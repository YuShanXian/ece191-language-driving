import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json,math
from pathlib import Path
from datetime import datetime
out=Path(__file__).parents[1]/'results'
config=json.loads((out/'timeout-and-four-changes.json').read_text())
start=config['start_ms']/1000
end=config['end_ms']/1000
events=[json.loads(l) for l in (Path(__file__).resolve().parents[3]/'logs/events.jsonl').read_text().splitlines()]
events=[e for e in events if start<=datetime.fromisoformat(e['time'].replace('Z','+00:00')).timestamp()<=end]
session=next(e['session_id'] for e in events if e['type']=='activated' and e.get('action')=='lane_change_left')
events=[e for e in events if e.get('session_id')==session]
terminal=[e for e in events if e['type'] in ['completed','timed_out','error','blocked','unsupported','cancelled']]
expected=[('lane_change_left','timed_out'),('go_straight','completed'),('lane_change_right','completed'),('lane_change_left','completed'),('lane_change_right','completed'),('lane_change_left','completed')]
assert [(e['action'],e['type']) for e in terminal]==expected
checks=[]
for e in terminal[1:]:
 assert math.dist(e['state']['xy'],e['execution']['expected_finish']['xy'])<.4
 turns=[m for m in e['journey']['observed_movements'] if m['action']!='go_straight' and not m.get('road_bend')]
 assert not turns
 if e['action'].startswith('lane_change'):
  request=json.loads(((Path(__file__).resolve().parents[3]/'logs/requests')/(e['request_id']+'.json')).read_text())
  proof=request['result']['route']['lane_change']
  assert proof['lane_delta']==(-1 if e['action']=='lane_change_left' else 1)
  checks.append(proof)
report=dict(passed=True,session_id=session,expected=expected,lane_changes=checks)
(out/'auxiliary-audit.json').write_text(json.dumps(report,indent=2))
print('Timeout followed by straight and four alternating one-lane changes: passed')
