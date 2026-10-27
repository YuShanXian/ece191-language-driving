import json
from mtr_project.paths import ROOT
from execute_language_plan_v4 import execute
p=next((ROOT/'runs/project-v3/llm-parser-v3').glob('*/parsed.json'));plan=json.loads(p.read_text());st=plan['stages'][-1];st.update(travel_distance_m=30,target_speed_mps=3,trigger='now');plan['stages']=[st]
r=execute(7,plan);assert r['status']=='completed_offline';assert max(r['speed_mps'])<=3.01;assert r['speed_mps'][-1]==0;print('Finite speed target 3 m/s, 30 m stop: passed',r['stages'][-1]['traveled_distance_m'])
(ROOT/'runs/project-v3/map-navigation-v4/finite-speed-test.json').write_text(json.dumps(r,indent=2))
