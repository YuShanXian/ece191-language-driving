"""Map-target grounding for offline lane changes; risks remain annotations."""
import numpy as np
from shapely.geometry import Point
from trajectory_checks import tangent,angle_diff,headings
from instruction_priority_selector import describe,evidence

def forward_nodes(graph,start,depth=8):
 seen={start};front={start}
 for _ in range(depth):
  front={b for a in front for b,r in graph.edges.get(a,{}).items() if r=='forward'}-seen
  seen|=front
 return seen

def lane_targets(graph,starts,direction):
 targets=[]
 for start in starts:
  current=forward_nodes(graph,start)
  for target,relation in graph.edges.get(start,{}).items():
   if relation!=direction:continue
   branch=forward_nodes(graph,target)
   unique=branch-current
   if unique:targets.append({'start':start,'target':target,'nodes':unique,'continuation':branch})
 return targets

def target_evidence(points,heading,graph,targets):
 angles=headings(points,heading)
 best=None
 for target in targets:
  hits=[]
  for i,(p,h) in enumerate(zip(points,angles)):
   for key in target['nodes']:
    node=graph.nodes[key]
    if node.polygon.buffer(.05).covers(Point(p)) and abs(angle_diff(h,tangent(node.baseline,p)))<np.radians(35):
     hits.append((i,key));break
  # Require a consecutive 0.5s visit to the neighbor branch, not just a crossed polygon.
  longest=0;streak=0;last=-2
  for step,key in hits:
   streak=streak+1 if step==last+1 else 1;last=step;longest=max(longest,streak)
  if longest<6:continue
  final=sum(any(graph.nodes[k].polygon.buffer(.05).covers(Point(p)) and abs(angle_diff(h,tangent(graph.nodes[k].baseline,p)))<np.radians(35) for k in target['continuation']) for p,h in zip(points[-6:],angles[-6:]))
  if final<6:continue
  item={'start_node':target['start'],'adjacent_target':target['target'],'visited_target_nodes':list(dict.fromkeys(k for _,k in hits)),'longest_target_visit_steps':longest,'end_center_in_target_branch':True}
  if best is None or longest>best['longest_target_visit_steps']:best=item
 return best

def select_priority(rows,trajectories,center,action,graph=None,start_nodes=None):
 targets=lane_targets(graph,start_nodes,action.rsplit('_',1)[1]) if action.startswith('lane_change_') else None
 scored=[];provisional=[]
 for row,xy in zip(rows,trajectories):
  p=np.vstack([center[:2],xy]);f=describe(p,float(center[6]),row)
  if targets is not None:
   target=target_evidence(p,float(center[6]),graph,targets)
   if target:ev='map_lane_target';f['lane_target']=target
   else:
    if evidence(f,action):provisional.append(row['candidate'])
    continue
  else:ev=evidence(f,action)
  if ev is None:continue
  tier=2 if ev in ('road_and_geometry','map_lane_target') else 1
  scored.append((tier,float(row['score']),row,f,ev))
 details={'geometry_only_candidates_not_confirmed_as_lane_change':provisional}
 if targets is not None:details['available_adjacent_targets']=[{'start':t['start'],'target':t['target']} for t in targets]
 if not scored:return {'candidate':None,'status':'no_adjacent_map_target' if targets==[] else 'no_action_candidate','matching_candidates':[],**details}
 _,_,row,f,ev=max(scored,key=lambda t:(t[0],t[1],-t[2]['candidate']))
 flags=list(row['rejected_by'])
 if len(start_nodes or [])>1:flags.append('ambiguous_start_lane')
 return {'candidate':row['candidate'],'status':'selected_for_offline_review','evidence':ev,'features':f,'model_score':row['score'],
 'risk_flags':flags,'passes_existing_checks':row['passes_current_checks'],
 'unassessed':['traffic_light','lane_marking_legality','interactive_traffic_response'],
 'matching_candidates':[r[2]['candidate'] for r in scored],**details,
 'scope':'Offline instruction priority; map target visit is not full safety or legality certification.'}
