import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
"""Independently verify both browser cancellation replans against map geometry."""
import sys,json,pickle,math
from pathlib import Path
from datetime import datetime
import numpy as np
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parent))
from engine.geometry import arc,footprint,angle_diff
from fixtures import load_scene
scene=load_scene(1)
cfg=json.loads((root/'results/browser-run-config.json').read_text())
logs=Path(__file__).resolve().parents[3]/'logs'
events=[json.loads(line) for line in (logs/'events.jsonl').read_text().splitlines()]
checks=[]
for name in ('cancel','cancel_late'):
 done=next(e for e in events if cfg[name]['start']<=e['time']<=cfg[name]['end'] and e['type']=='completed' and e['action']=='turn_right')
 request=json.loads((logs/'requests'/(done['request_id']+'.json')).read_text())
 r=request['result'];state=request['request']['state'];route=r['route']
 assert route['junction_replan']['previous_connector']=='C63948'
 assert route['junction_replan']['incoming_lane']=='L63477'
 assert route['junction_replan']['target']=='L67611'
 pts=np.array(route['points']);pts=pts[arc(pts)<=route['segments'][0]['end']+.001]
 d=np.gradient(pts,axis=0);dd=np.gradient(d,axis=0)
 hs=np.arctan2(d[:,1],d[:,0]);k=np.abs(d[:,0]*dd[:,1]-d[:,1]*dd[:,0])/np.maximum(np.linalg.norm(d,axis=1)**3,1e-8)
 assert math.dist(pts[0],state['xy'])<.0001
 assert abs(angle_diff(hs[0],state['heading']))<.08
 assert k.max()<.222
 assert max(np.unwrap(hs)-hs[0])<.06
 assert all(scene.graph.surface.covers(footprint(p,h,4.8,2)) for p,h in zip(pts,hs))
 assert done['state']['node_id']=='L67611'
 checks.append(dict(case=name,start=state['xy'],finish=done['state']['xy'],target='L67611',
   footprint_samples=len(pts),max_curvature=float(k.max()),min_turn_radius_m=float(1/k.max())))
(root/'results/browser-redirect-geometry.json').write_text(json.dumps(checks,indent=2))
print(json.dumps(checks))
