from pathlib import Path
import sys,json
sys.path.insert(0,'historical-project/scripts')
from execute_language_plan_v4 import execute
r=Path('historical-project');out=r/'runs/project-v3/multistep-v15';rows=json.loads((out/'results.json').read_text());checks=[]
for row in rows:
 d=Path(row['run'].replace('D:\\','historical-drive/').replace('\\','/'));p=json.loads((d/'parsed.json').read_text());e=json.loads((d/'execution.json').read_text());st=e['stages'];assert len(st)==5
 for a,b in zip(p['stages'],st):
  if a.get('travel_distance_m') is not None:assert abs(b.get('traveled_distance_m',-100)-a['travel_distance_m'])<.25
  if a.get('stop_at_end'):assert b.get('final_speed_mps',0)<.05
 checks.append({'group':row['group'],'distance_and_stop_checks':True})
state=json.loads((out/'state.json').read_text());base=p['stages'][0].copy();base.update(action='reverse',travel_distance_m=2,trigger='now',target_text='',constraints=[],completion_text='',stop_at_end=True)
invalid={**base,'action':'navigate_to','travel_distance_m':None,'trigger':'after_previous','target_text':'unmapped destination'};later={**base,'action':'go_straight','trigger':'after_previous','travel_distance_m':5};plan={'status':'parsed','unresolved_text':[],'stages':[base,invalid,later,later,later]};e=execute(7,plan,state,'free');assert e['status']=='partial' and len(e['stages'])==2;checks.append({'test':'blocked second step prevents steps3-5','passed':True});(out/'additional-checks.json').write_text(json.dumps(checks,indent=2));print(len(checks),'checks passed')
