import json,math
from mtr_project.paths import ROOT
from execute_language_plan_v4 import execute
base=ROOT/'runs/project-v3/llm-parser-v4'
folder=base/'20261020-210406-975-f54e8941'
state=json.loads((folder/'start-state.json').read_text(encoding='utf-8-sig'))
plan=json.loads((folder/'parsed.json').read_text())
previous=json.loads((base/'20261020-210346-955-5a76972f'/'execution.json').read_text())
p=previous['points'];end=p[-1]
for q in reversed(p[:-1]):
 if math.dist(end,q)>.01:
  corrected=math.atan2(end[1]-q[1],end[0]-q[0]);break
results=[]
for heading in [state['heading'],corrected]:
 state['heading']=heading
 r=execute(7,plan,state)
 results.append({'heading':heading,'status':r['status'],'stages':r['stages']})
print(json.dumps(results,indent=2))
(ROOT/'runs/project-v3/live-replanning-v6/distance60-diagnosis.json').write_text(json.dumps(results,indent=2))

plan['stages'][0]['travel_distance_m']=30
r=execute(7,plan,state)
print(json.dumps({'test':'same position, 30 meters','status':r['status'],'stages':r['stages']},indent=2))
assert r['status']=='completed_offline'
