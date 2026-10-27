import sys,json,pickle,math,time
from pathlib import Path
import numpy as np
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parent))
import engine.planner as planner
from engine.geometry import arc,tangent,angle_diff,footprint,validate_path
from engine.junction_replan import replan
from fixtures import load_scene
scene=load_scene(1);planner.get_scene=lambda n:scene
req=json.loads((root/'results/cancel-right-failed.json').read_text())['request']
before=scene.nodes['C63948'].baseline.wkt
results=[]
def check(state,action):
 t=time.perf_counter();r=planner.plan(dict(req,state=state,stage=planner.stage(action)))
 assert r['status']=='ready',(action,state['xy'],r.get('reason'))
 route=r['route'];proof=route['junction_replan'];p=np.asarray(route['points'])
 assert np.linalg.norm(p[0]-state['xy'])<.0001
 assert validate_path(p)[0]
 end=route['segments'][0]['end'];s=arc(p);curve=p[s<=end+.001]
 h=np.arctan2(*np.gradient(curve,axis=0)[:,::-1].T)
 assert abs(angle_diff(h[0],state['heading']))<.08
 assert all(scene.graph.surface.covers(footprint(x,y,4.8,2)) for x,y in zip(curve,h))
 turns=[m for m in route['movements'] if m['action']!='go_straight' and not m['road_bend']]
 assert all(m['action']==action for m in turns)
 if action=='turn_right':assert max(np.unwrap(h)-h[0])<.06,'unrequested left first'
 results.append(dict(action=action,xy=state['xy'],source=r['route_source'],planning_ms=(time.perf_counter()-t)*1000))
 return r
r=check(req['state'],'turn_right')
(root/'results/cancel-right-fixed.json').write_text(json.dumps(r,indent=2))
for key,actions in [('C63948',['turn_right','go_straight']),('J_L63477_L67611',['turn_left','go_straight']),('J_L63477_L67723',['turn_left','turn_right'])]:
 line=scene.nodes[key].baseline
 for distance in ((1,3,5,7,12,17) if key=='C63948' else (1,3,5,7)):
  p=line.interpolate(distance);state=dict(req['state'],xy=list(p.coords[0]),heading=tangent(line,p),node_id=key)
  # Some right-curves have already committed after 7 m; those require reversing.
  if abs(angle_diff(state['heading'],tangent(scene.nodes['L63477'].baseline,scene.nodes['L63477'].baseline.coords[-1])))>math.radians(20):continue
  for action in actions:check(state,action)
late=scene.nodes['C63948'].baseline;point=late.interpolate(late.length*.7)
state=dict(req['state'],xy=list(point.coords[0]),heading=tangent(late,point),node_id='C63948')
assert replan(scene,state,'turn_right') is None
assert scene.nodes['C63948'].baseline.wkt==before
(root/'results/junction-replan.json').write_text(json.dumps(results,indent=2))
print('PASS',len(results),'live-pose redirects; late turn rejected; original graph unchanged',flush=True)
