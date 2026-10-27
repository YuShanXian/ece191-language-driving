from pathlib import Path
import json,sys,numpy as np
sys.path.insert(0,'historical-project/scripts')
from execute_language_plan_v4 import execute
r=Path('historical-project');rows=json.loads((r/'runs/project-v3/basic-commands-v14/tests.json').read_text());out=[]
for row in rows:
 d=Path(row['run'].replace('D:\\','historical-drive/').replace('\\','/'));p=json.loads((d/'parsed.json').read_text());state=json.loads((d/'start-state.json').read_text());e=execute(7,p,state,'free');pts=np.asarray(e['points']);acts=[s['action'] for s in p['stages']];semantic=acts==row['expected'] or (row['expected']==['pull_over'] and acts==['pull_over','stop'])
 out.append({'case':row['case'],'text':row['text'],'understood':semantic,'status':e['status'],'start_error_m':float(np.linalg.norm(pts[0]-state['xy'])) if e['status']!='live_control' else None,'stages':e.get('stages',[]),'commands':e.get('commands',[])})
 if row['case']==7:assert e['stages'][-1]['traveled_distance_m']==0
 if row['case']==11:assert all(s.get('traveled_distance_m',0)<100 for s in e['stages'])
 if row['case'] in (5,6):assert e['status']=='completed_offline'
 if row['case']==1:assert e['commands'][0]['action']=='cancel'
 print(row['case'],semantic,e['status'],flush=True)
(r/'runs/project-v3/basic-commands-v14/rechecked.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
