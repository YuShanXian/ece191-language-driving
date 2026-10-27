import json,numpy as np
from mtr_project.paths import ROOT,write_json
from select_review_instruction import resolve
out=ROOT/'runs/project-v3/automatic-road-v9';rows=json.loads((out/'trajectory-results.json').read_text())['rows'];assert len(rows)==35
checks=[]
for r in rows:
 answer=resolve(r['scene'],r['instruction']);assert answer['policy']=='automatic_roads';assert answer['status']==r['status'];arr=np.load(answer['trajectory_file'])[answer['trajectory_key']];assert arr.ndim==2 and arr.shape[1]==2 and np.isfinite(arr).all();checks.append({'scene':r['scene'],'command':r['command'],'default_policy':'automatic_roads','points':len(arr)})
assert resolve(1,'do something mysterious')['status']=='unsupported_instruction'
assert resolve(1,'Turn left then turn right')['status']=='unsupported_trigger_or_sequence_for_cached_demo'
write_json(out/'entrypoint-verification.json',{'passed':True,'cases':checks,'unsupported_and_sequence_checks':True});print('All 35 default CLI resolutions and finite trajectories passed; unsupported input and sequence rejection passed.')
