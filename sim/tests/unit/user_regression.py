import sys,json,pickle,math,time
from pathlib import Path
import numpy as np
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parent))
import engine.planner as planner
from engine.geometry import footprint,arc,angle_diff
from fixtures import load_scene
scene=load_scene(1);planner.get_scene=lambda n:scene
reports=[]
for name in ('user-step7-first','user-step7-failed','user-step8-failed'):
 fixture=json.loads((root/'results'/f'{name}.json').read_text());req=fixture['request']
 start=time.perf_counter();r=planner.plan(req);ms=(time.perf_counter()-start)*1000
 if 'step7' in name:
  assert r['status']=='waiting' and r['diagnostics']['code']=='opposing_lane_only'
 else:
  assert r['status']=='ready',r.get('reason')
  assert r['recovery']['kind']=='three_point' and len(r['phases'])==4
  assert [p['route'].get('reverse',False) for p in r['phases']]==[True,False,True,False]
  assert all(p['stop_at_end'] for p in r['phases'][:-1])
  for phase in r['phases'][1:]:
   pts=np.array(phase['route']['points']);s=arc(pts)
   # Include maneuver and target lane approach, not an unrelated remote map edge.
   pts=pts[s<=phase['completion_m']]
   d=np.gradient(pts,axis=0);hs=np.arctan2(d[:,1],d[:,0])+(math.pi if phase['route'].get('reverse') else 0)
   assert all(scene.graph.surface.covers(footprint(p,h,4.8,2)) for p,h in zip(pts,hs))
  for a,b in zip(r['phases'],r['phases'][1:]):assert math.dist(a['route']['points'][-1],b['route']['points'][0])<.02
  (root/'results/user-step8-fixed.json').write_text(json.dumps(r,indent=2))
 reports.append(dict(case=name,status=r['status'],reason=r['reason'],planning_ms=ms,recovery=r.get('recovery')))
print(json.dumps(reports,indent=2));(root/'results/user-regression.json').write_text(json.dumps(reports,indent=2))
