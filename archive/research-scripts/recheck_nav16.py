import sys,json
from pathlib import Path
sys.path.insert(0,'historical-project/scripts')
from execute_language_plan_v4 import execute
r=Path('historical-project');out=r/'runs/project-v3/navigation-combos-v16';rows=json.loads((out/'results.json').read_text());(out/'initial-results.json').write_text(json.dumps(rows,indent=2))
for row in rows:
 d=Path(row['run'].replace('D:\\','historical-drive/').replace('\\','/'));p=json.loads((d/'parsed.json').read_text());e=execute(row['scene'],p,json.loads((d/'start-state.json').read_text()),'free');(d/'execution-v16.json').write_text(json.dumps(e));row.update(status=e['status'],stages=e['stages'],end_speed=e['speed_mps'][-1]);
 if e['status']=='completed_offline':assert e['speed_mps'][-1]==0 and not e.get('follow_route',{}).get('available')
 print(row['case'],row['status'],row['end_speed'],flush=True)
(out/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
