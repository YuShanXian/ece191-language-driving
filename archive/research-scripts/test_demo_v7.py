import json,math
from mtr_project.paths import ROOT
from execute_language_plan_v4 import execute
base=ROOT/'runs/project-v3/llm-parser-v4';f=base/'20261020-210406-975-f54e8941'
p=json.loads((f/'parsed.json').read_text());state=json.loads((f/'start-state.json').read_text(encoding='utf-8-sig'));state['heading']=-.14676319624345294
r=execute(7,p,state);print('ROAD END',r['status'],r['stages'],flush=True)
assert r['status']=='completed_offline' and r['stages'][0]['stopped_at_road_end'] and r['speed_mps'][-1]==0
p['stages'][0].update(action='u_turn',source_clause='Make a U-turn',travel_distance_m=None,stop_at_end=False)
results={'road_end':r,'uturns':[]}
for scene in range(1,8):
 r=execute(scene,p);results['uturns'].append(r);print('UTURN',scene,r['status'],[(x.get('reason'),x.get('path')) for x in r['stages']],flush=True)
out=ROOT/'runs/project-v3/live-replanning-v7';out.mkdir(exist_ok=True);(out/'checks.json').write_text(json.dumps(results,indent=2))
