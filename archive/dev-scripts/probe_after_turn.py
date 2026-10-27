import sys,json,pickle
from pathlib import Path
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parents[1]/'sim'))
import engine.planner as p
s=pickle.loads((root/'results/scene1.pkl').read_bytes());p.get_scene=lambda _:s
r=json.loads((root/'results/minimized-timing-regression.json').read_text())[0]
state=r['state']
for a in ['go_straight','turn_left','turn_right','u_turn','lane_change_left','lane_change_right']:
 t=p.plan(dict(scene=1,state=state,stage=p.stage(a)))
 print(a,t['status'],t.get('route_source'),t.get('completion_m'),t.get('reason'))
