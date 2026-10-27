"""Follow the road to its real map end before enabling free recovery."""
import math,heapq
import numpy as np
from shapely.geometry import Point
from trajectory_checks import tangent,angle_diff
def at_road_end(scene,stage,state):
 from free_navigation_v8 import context,recover
 from navigation_turn_v15 import locate
 g,c,rot=context(scene);p=c[:2]+np.asarray(state['xy'])@rot.T;h=c[6]+state['heading'];key=locate(g,p,h)
 if key is None:return None
 start=g.nodes[key].baseline.project(Point(p));queue=[(g.nodes[key].baseline.length-start,[key])];chosen=None
 while queue:
  length,path=heapq.heappop(queue)
  if length>250 or len(path)>20:continue
  k=path[-1];edges=[n for n,rel in g.edges.get(k,{}).items() if rel=='forward' and n not in path]
  if not edges:chosen=path;break
  for n in edges:
   line=g.nodes[n].baseline;a=np.asarray(line.coords[0])[:2];b=np.asarray(line.coords[-1])[:2]
   if abs(angle_diff(tangent(line,b),tangent(line,a)))<math.radians(30):heapq.heappush(queue,(length+line.length,path+[n]))
 if chosen is None:return None
 guide=[p]
 for i,k in enumerate(chosen):
  line=g.nodes[k].baseline;s=start if i==0 else 0.
  guide.extend(np.asarray(line.interpolate(float(v)).coords[0])[:2] for v in np.r_[np.arange(s+.3,line.length,.3),line.length])
 guide=np.asarray(guide);guide=guide[np.r_[True,np.linalg.norm(np.diff(guide,axis=0),axis=1)>1e-6]]
 if len(guide)<2:return None
 arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(guide,axis=0),axis=1))];n=max(1,int(math.ceil(arc[-1]/2.5/.1)));s=np.linspace(0,arc[-1],n+1);pp=np.column_stack([np.interp(s,arc,guide[:,j]) for j in range(2)]);local=(pp-c[:2])@rot
 endh=tangent(g.nodes[chosen[-1]].baseline,pp[-1])-c[6];end={**state,'xy':local[-1].tolist(),'heading':endh,'speed':2.5,'history':state.get('history',[])+local.tolist()}
 if 'view_bounds' in end:
  dx,dy=local[-1]-state['xy'];b=end['view_bounds'];end['view_bounds']=[b[0]+dx,b[1]+dx,b[2]+dy,b[3]+dy]
 result=recover(scene,stage,end)
 if result['status']!='completed_offline':return None
 points=local.tolist()+result['points'][1:];speeds=[2.5]*len(local)+result['speed_mps'][1:];row=dict(result['stages'][0]);row.update(start_point=0,end_point=len(points)-1,approach_path=chosen,approach_distance_m=float(arc[-1]),traveled_distance_m=float(arc[-1])+row.get('traveled_distance_m',0),reason=f'Follow the road for {arc[-1]:.1f} m to its end, then use free-mode recovery to reach a mapped road.');return {**result,'points':points,'speed_mps':speeds,'stages':[row]}
