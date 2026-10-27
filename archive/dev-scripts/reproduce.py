import sys,json,pickle,time
from pathlib import Path
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parents[1]/'sim'))
import engine.planner as planner
from engine.geometry import validate_path
with (root/'results/scene1.pkl').open('rb') as f:scene=pickle.load(f)
planner.get_scene=lambda n:scene
for action in ['turn_right','u_turn']:
 req=json.loads((root/'results'/(action+'-failed.json')).read_text())['request']
 req['state']['speed']=0
 t=time.perf_counter();res=planner.plan(req)
 print(action,res['status'],res.get('route_source'),res.get('reason'),'ms',(time.perf_counter()-t)*1000,flush=True)
 print('PREP',res.get('route',{}).get('preparation'),'RECOVERY',res.get('recovery'),flush=True)
 (root/'results'/(action+'-fixed.json')).write_text(json.dumps(res,indent=2))
 assert res['status']=='ready'
 for p in res.get('phases',[res]):assert validate_path(p['route']['points'])[0]
