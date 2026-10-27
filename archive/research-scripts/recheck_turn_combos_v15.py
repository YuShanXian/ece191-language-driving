import json,sys
from pathlib import Path
sys.path.insert(0,'historical-project/scripts')
from execute_language_plan_v4 import execute
r=Path('historical-project');o=r/'runs/project-v3/multistep-v15';rows=json.loads((o/'results.json').read_text());(o/'initial-results.json').write_text(json.dumps(rows,indent=2))
for row in rows[10:]:
 d=Path(row['run'].replace('D:\\','historical-drive/').replace('\\','/'));p=json.loads((d/'parsed.json').read_text());e=execute(7,p,json.loads((d/'start-state.json').read_text()),'free');(d/'execution.json').write_text(json.dumps(e));row['execution_status']=e['status'];row['stages']=e['stages'];row['execution_complete_in_order']=e['status']=='completed_offline' and [s['action'] for s in p['stages']]==[s['action'] for s in e['stages']];print(row['group'],row['execution_complete_in_order'],e['status'],flush=True)
(o/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
