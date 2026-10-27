import json,math
from pathlib import Path
p=Path('historical-project/runs/project-v3/refactor-v35')
c=json.loads((Path(__file__).parents[1]/'results/browser-run-config.json').read_text())['bend']
for e in map(json.loads,(p/'events.jsonl').read_text().splitlines()):
 if not c['start']<=e['time']<=c['end'] or e['type']!='completed':continue
 a=e['state'];b=e['execution']['expected_finish']
 if a.get('node_id')==b.get('node_id'):continue
 r=json.loads((p/'requests'/(e['request_id']+'.json')).read_text())['result']
 print(e['action'], 'error',math.dist(a['xy'],b['xy']),'actual',a,'expected',b,'proof',r['route'].get('lane_change'))
 print('boundary',[(x,y) for x,y in zip(r['route']['segments'],r['route']['segments'][1:]) if x['node_id']==a['node_id'] and y['node_id']==b['node_id']])
