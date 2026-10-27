import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json
from datetime import datetime
from pathlib import Path
p=Path(__file__).parents[1]/'results'
events=json.loads((p/'user-session.json').read_text())
def seconds(t):return datetime.fromisoformat(t.replace('Z','+00:00')).timestamp()
start=seconds(events[0]['time']);inputs=[]
for e in events:
 if e['type']=='queued':
  for stage in e['stages']:
   inputs.append(dict(at=seconds(e['time'])-start,stage=stage,action=stage['action'],timeout=e['timeout']))
 elif e['type']=='cancelled':inputs.append(dict(at=seconds(e['time'])-start,action='cancel'))
spec=dict(name='original-user-stop-replay',scene=1,latency=.05,limit=210,afterCompletionSeconds=20,inputs=inputs)
(p/'original-user-stop-spec.json').write_text(json.dumps(spec,indent=2))
print([(round(x['at'],2),x['action']) for x in inputs])
