import json,numpy as np
from mtr_project.paths import ROOT,write_json
from select_review_instruction import resolve
out=ROOT/'runs/project-v3/centerline-planner-v1';rows=json.loads((out/'results.json').read_text())['rows'];assert len(rows)==35;tests=[]
for r in rows:
 answer=resolve(r['scene'],r['instruction'],policy='centerline_planner');assert answer['status']=='offline_plan_output';p=np.load(answer['trajectory_file'])[answer['trajectory_key']];assert p.shape==(121,2) and np.isfinite(p).all();assert r['source']=='deterministic_map_centerline';tests.append({'scene':r['scene'],'command':r['command'],'points':len(p),'finite':True})
write_json(out/'entrypoint-verification.json',{'passed':True,'tests':tests});print('35 pure-program plan outputs verified, each 121 finite points across 12 seconds.')
