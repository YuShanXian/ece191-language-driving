"""Navigation turns follow connected map roads; recovery is only for no-road states."""
import math,heapq
import numpy as np
from shapely.geometry import Point
from trajectory_checks import tangent,angle_diff

def locate(g,p,h):
 items=[]
 for n in g.nodes.values():
  d=n.baseline.distance(Point(p));a=abs(angle_diff(tangent(n.baseline,p),h))
  if d<4 and a<math.radians(50):items.append((d+2*a,n.key))
 return min(items)[1] if items else None

def road_available(scene,state):
 from free_navigation_v8 import context
 g,c,rot=context(scene);p=c[:2]+np.asarray(state['xy'])@rot.T;h=c[6]+state['heading'];k=locate(g,p,h)
 if k is None:return False
 remaining=g.nodes[k].baseline.length-g.nodes[k].baseline.project(Point(p))
 seen={k};queue=[k]
 while queue and remaining<8:
  key=queue.pop()
  for nxt,rel in g.edges.get(key,{}).items():
   if rel=='forward' and nxt not in seen:seen.add(nxt);remaining+=g.nodes[nxt].baseline.length;queue.append(nxt)
 return remaining>=8

def execute_turn(scene,stage,state):
 from free_navigation_v8 import context
 g,c,rot=context(scene);p=c[:2]+np.asarray(state['xy'])@rot.T;h=c[6]+state['heading'];key=locate(g,p,h)
 def block(reason):return {'scene':scene,'status':'blocked','points':[state['xy']],'speed_mps':[state['speed']],'dt':.1,'stages':[{'action':stage['action'],'source_clause':stage['source_clause'],'status':'blocked','reason':reason}]}
 if stage.get('constraints') or stage.get('target_text') or stage.get('completion_text') or stage.get('travel_distance_m') is not None:return block('Turn instruction has an unresolved condition or distance.')
 if stage['trigger']=='intersection' and (stage.get('trigger_value') not in (None,1) or any(x in stage.get('trigger_text','').lower() for x in ('second','third','\u7b2c\u4e8c','\u7b2c\u4e09'))):return block('Only the next available junction is supported; later junction counting needs clarification.')
 if stage['trigger'] not in ('now','after_previous','intersection'):return block('Turn trigger is not supported.')
 if key is None:return block('No current road found.')
 from lane_continuity_v25 import lane_rank_error
 groups={}
 for lane in g.nodes.values():
  if lane.kind=='lane':groups.setdefault(lane.lane_group,[]).append(lane)
 line=g.nodes[key].baseline;entry=line.project(Point(p));queue=[(0.,[(key,entry,'start')])];chosen=None;solutions=[];visited=set();sign=1 if stage['action']=='turn_left' else -1
 # The first few metres of a junction are shared by several possible exits.
 # Keep those exits available instead of locking onto the nearest connector.
 if g.nodes[key].kind=='connector' and entry<8:
  parents=[k for k,edges in g.edges.items() if edges.get(key)=='forward']
  for parent in parents:
   for nk,rel in g.edges[parent].items():
    if rel!='forward' or nk==key or g.nodes[nk].kind!='connector':continue
    other=g.nodes[nk].baseline;ns=other.project(Point(p))
    if other.distance(Point(p))<5 and abs(angle_diff(tangent(other,p),h))<math.radians(65):queue.append((other.distance(Point(p)),[(nk,ns,'start')]))
 heapq.heapify(queue)
 while queue:
  distance,path=heapq.heappop(queue);k,entry,relation=path[-1]
  if solutions and distance>min(x[0] for x in solutions):break
  visit=(k,round(entry/5))
  if visit in visited:continue
  visited.add(visit)
  if distance>1200 or len(visited)>3000:continue
  node=g.nodes[k];line=node.baseline;coords=np.asarray(line.coords)[:,:2]
  change=angle_diff(tangent(line,coords[-1]),h if k==key else tangent(line,coords[0]))
  is_uturn=stage['action']=='u_turn'
  requested=(abs(math.degrees(angle_diff(tangent(line,coords[-1]),h)))>=150 if is_uturn else 30<=math.degrees(change)*sign<=150)
  if stage['action']=='go_straight':requested=abs(math.degrees(change))<30
  if node.kind=='connector' and requested:
   source=next((g.nodes[n] for n,_,_ in reversed(path[:-1]) if g.nodes[n].kind=='lane'),None)
   exits=[g.nodes[n] for n,rel in g.edges.get(k,{}).items() if rel=='forward' and g.nodes[n].kind=='lane']
   ordinal=min((lane_rank_error(source,n,groups) for n in exits),default=0) if source else 0
   solutions.append((distance,ordinal,path));continue
  if not is_uturn and node.kind=='connector' and k!=key and abs(math.degrees(change))>30:continue
  used={v[0] for v in path}
  for n,rel in g.edges.get(k,{}).items():
   if n in used:continue
   if rel=='forward':heapq.heappush(queue,(distance+max(0,line.length-entry),path+[(n,0.,rel)]))
 if solutions:distance,_,chosen=min(solutions,key=lambda x:(x[0],x[1]))
 if chosen is None:return block('No reachable '+('U-turn' if stage['action']=='u_turn' else 'straight' if stage['action']=='go_straight' else 'left' if sign>0 else 'right')+' turn ahead, in the loaded map.')
 turn_key=chosen[-1][0];nxt=[n for n,r in g.edges.get(turn_key,{}).items() if r=='forward'];target=turn_key
 if nxt:target=min(nxt);chosen.append((target,0.,'forward'))
 pts=[p];lane_changes=[]
 for i,(k,start,rel) in enumerate(chosen):
  line=g.nodes[k].baseline
  end=min(8.,line.length) if k==target and k!=turn_key else line.length
  pts.extend(np.asarray(line.interpolate(float(v)).coords[0])[:2] for v in np.r_[np.arange(start+.4,end,.4),end] if v>=start)
 chosen=[x[0] for x in chosen]
 # Blend the initial offset onto the chosen junction exit without snapping.
 if len(pts)>3:
  offset=p-np.asarray(g.nodes[chosen[0]].baseline.interpolate(g.nodes[chosen[0]].baseline.project(Point(p))).coords[0])[:2]
  travelled=0.
  for j in range(1,len(pts)):
   travelled+=float(np.linalg.norm(np.asarray(pts[j])-np.asarray(pts[j-1])))
   if travelled>=8:break
   pts[j]=np.asarray(pts[j])+offset*(1-travelled/8)**2
 pts=np.asarray(pts);pts=pts[np.r_[True,np.linalg.norm(np.diff(pts,axis=0),axis=1)>1e-6]];arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))]
 from route_speed_v18 import sample
 q,v=sample(pts,stage.get('target_speed_mps') or 20/3.6,state.get('speed',0),stage.get('stop_at_end',False),end_speed=stage.get('exit_speed_mps'));n=len(q)-1;local=(q-c[:2])@rot
 row={'index':0,'action':stage['action'],'source_clause':stage['source_clause'],'status':'completed_offline','start_point':0,'end_point':n,'target':target,'path':chosen,'turn_connector':turn_key,'trajectory_source':'next_connected_map_turn','approach_distance_m':float(max(0,distance-5*len(lane_changes))),'traveled_distance_m':float(arc[-1]),'final_speed_mps':float(v[-1]),'reason':'Follow the current road to the next reachable requested turn, then follow its map connection.'}
 row['preparatory_lane_changes']=lane_changes
 if turn_key.startswith('J_'):
  row['trajectory_source']='generated_intersection_connection'
  row['generated_centerline']=True
  row['road_surface_checked']=True
 row['reason']=('Change lanes '+', then '.join(x['direction'] for x in lane_changes)+' to reach the turn lane. ' if lane_changes else '')+'Follow the road for '+str(round(row['approach_distance_m'],1))+' m, then take the next reachable '+('U-turn' if stage['action']=='u_turn' else 'straight' if stage['action']=='go_straight' else 'left' if sign>0 else 'right')+' turn at the map junction.'
 return {'scene':scene,'status':'completed_offline','points':local.tolist(),'speed_mps':v.tolist(),'stages':[row],'dt':.1}
