import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json,shutil
from pathlib import Path
root=Path(__file__).parents[1];logs=(Path(__file__).resolve().parents[3]/'logs')
events=[json.loads(s) for s in (logs/'events.jsonl').read_text().splitlines()]
events=[e for e in events if e['time']>'2026-10-24T09:32:00Z']
(root/'results/user-session.json').write_text(json.dumps(events,indent=2))
for e in events:
 if e['type'] in ('queued','activated','completed','cancelled','timed_out','route_installed'):
  print(e['time'],e['type'],e.get('stage_id'),e.get('action'),e.get('state',{}).get('xy'),[x['action'] for x in e.get('stages',[])])
first=next(e for e in events if e['type']=='waiting' and e.get('stage_id')==27)
shutil.copyfile(logs/'requests'/(first['request_id']+'.json'),root/'results/user-step7-first.json')
