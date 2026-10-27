"""Navigation interpretation: choose an onward map branch before testing trajectories."""
import numpy as np
from shapely.geometry import Point
from trajectory_checks import tangent,angle_diff,headings
from instruction_priority_v2 import forward_nodes

def navigation_branches(graph,starts,heading):
 branches=[]
 for start in starts:
  approaches=[(start,False)]+[(n,True) for n,r in graph.edges.get(start,{}).items() if r in ('left','right')]
  for approach,adjacent in approaches:
   for key,relation in graph.edges.get(approach,{}).items():
    if relation!='forward':continue
    node=graph.nodes[key]
    end=np.asarray(node.baseline.coords[-1])[:2]
    delta=float(np.degrees(angle_diff(tangent(node.baseline,end),heading)))
    branches.append({'start':start,'approach':approach,'branch':key,'requires_lane_change':adjacent,'exit_heading_change_deg':delta})
 straight=[b for b in branches if abs(b['exit_heading_change_deg'])<=20]
 if straight:
  selected=min(straight,key=lambda b:(b['requires_lane_change'],abs(b['exit_heading_change_deg'])))
  mode='forward_road'
 else:
  current=[b for b in branches if not b['requires_lane_change']]
  if not current:return {'mode':'map_unresolved','branches':branches}
  selected=min(current,key=lambda b:abs(b['exit_heading_change_deg']))
  mode='follow_road_fallback'
 return {'mode':mode,'selected':selected,'branches':branches,'scope':'Current and immediately adjacent approach lanes; next mapped connection. No marking legality or global route search.'}

def branch_evidence(points,heading,graph,decision):
 if 'selected' not in decision:return None
 b=decision['selected'];allowed=forward_nodes(graph,b['branch'],2)
 angles=headings(points,heading)
 # Require the ending 0.5 s inside the selected onward branch and aligned with it.
 visits=[]
 for p,h in zip(points[-6:],angles[-6:]):
  hits=[k for k in allowed if graph.nodes[k].polygon.buffer(.05).covers(Point(p)) and abs(angle_diff(h,tangent(graph.nodes[k].baseline,p)))<np.radians(35)]
  if not hits:return None
  visits.append(min(hits,key=lambda k:graph.nodes[k].baseline.distance(Point(p))))
 return {'visited_target_nodes':list(dict.fromkeys(visits)),'navigation_branch':b['branch'],'end_center_in_target_branch':True}
