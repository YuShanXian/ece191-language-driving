import json,time,math
import numpy as np
from mtr_project.paths import ROOT
from execute_language_plan_v4 import execute
OUT=ROOT/'runs/project-v3/common-commands-v10'
state=json.loads((ROOT/'runs/project-v3/provider-benchmark-20261020/raw/cf615973-4c9b-447f-a2b4-c182a2141fef/start-state.json').read_text())
results=[];deadline=time.time()+900
while time.time()<deadline:
 rows=json.loads((OUT/'language-results.json').read_text(encoding='utf-8'))
 for row in rows:
  if any(r['case']==row['case'] for r in results):continue
  if not row.get('parsed'):continue
  try:
   expected=row['expected'];pose=state if expected==['u_turn'] else None
   r=execute(7,row['parsed'],pose,mode='free');normal=expected not in [['NO_ACTION'],['CLARIFY'],['CONDITION'],['GROUNDING']]
   okay=r['status'] in ('completed_offline','live_control') if normal else r['status'] not in ('completed_offline','live_control')
   if normal and expected==['u_turn']:
    s=r['stages'][0];okay=okay and bool(s.get('target')) and s.get('endpoint_centerline_distance_m',999)<.3 and r.get('follow_route',{}).get('available',False)
   if r['status']=='live_control' and row.get('expected_speed') is not None:okay=okay and any(abs((c.get('speed_mps') or 0)-row['expected_speed'])<.001 for c in r['commands'])
   if len(expected)>1 and row.get('expected_speed')==15:okay=okay and r.get('target_speed_mps')==15
   item={'case':row['case'],'text':row['text'],'execution_passed':bool(okay),'status':r['status'],'stages':[{'action':s['action'],'status':s['status'],'reason':s.get('reason'),'target':s.get('target')} for s in r.get('stages',[])]}
   (OUT/('execution-'+str(row['case'])+'.json')).write_text(json.dumps(r))
  except Exception as e:item={'case':row['case'],'text':row['text'],'execution_passed':False,'error':str(e)}
  results.append(item);(OUT/'execution-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(item,ensure_ascii=False),flush=True)
 if len(results)>=44:break
 time.sleep(2)
