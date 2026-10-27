import sys,json
from pathlib import Path
sys.path.insert(0,'historical-project/scripts')
from execute_language_plan_v3 import execute
r=Path('historical-project/runs/project-v3/provider-benchmark-20261020/raw/4d435501-fd15-4fdb-ab57-a4f0b9608013');e=json.loads((r/'execution.json').read_text());p=json.loads((r/'parsed.json').read_text());s={'xy':e['points'][-1],'heading':e['heading_rad'][-1],'speed':e['speed_mps'][-1]};x=execute(7,{**p,'stages':[p['stages'][1]]},s,'free');print(x['status'],x['stages'])
