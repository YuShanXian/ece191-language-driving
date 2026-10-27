import json, time, math
import numpy as np
from mtr_project.paths import ROOT
from execute_language_plan_v4 import execute
OUT=ROOT/'runs/project-v3/navigation-modes-v8';OUT.mkdir(exist_ok=True)
raw=ROOT/'runs/project-v3/provider-benchmark-20261020/raw/f9624d8f-52bf-4e5b-9ed2-387b3941e5e3'
plan=json.loads((raw/'parsed.json').read_text());state=json.loads((raw/'start-state.json').read_text())
for mode in ('safe','free'):
 t=time.time();r=execute(7,plan,state,mode=mode);(OUT/(mode+'-road-end-repro.json')).write_text(json.dumps(r))
 print(json.dumps({'mode':mode,'status':r['status'],'seconds':round(time.time()-t,2),'stages':r['stages']},ensure_ascii=False),flush=True)
