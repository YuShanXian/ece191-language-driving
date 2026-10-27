import sys,json,pickle
from pathlib import Path
root=Path(__file__).parents[1];sys.path[:0]=[str(root.parents[1]/'sim'),str(root/'tests')]
from engine.scene import get_scene
from availability_oracle import classify
cache={};rows=[]
for file in sorted((root/'results/random').glob('*.json')):
 r=json.loads(file.read_text());number=r['spec']['scene']
 if number not in cache:
  saved=root/'results'/f'scene{number}.pkl'
  cache[number]=pickle.loads(saved.read_bytes()) if saved.exists() else get_scene(number)
  if not saved.exists():saved.write_bytes(pickle.dumps(cache[number]))
 for o in r['outcomes']:
  if o['status'] in ('completed','applied','cancelled'):continue
  req=next((x for x in reversed(r['requests']) if str(x['id'])==o.get('request_id')),None)
  verdict=classify(cache[number],req['request']) if req else {'classification':'not_reached'}
  row=dict(seed=r['spec']['seed'],scene=number,action=o['action'],status=o['status'],planner_reason=o['reason'],**verdict)
  if verdict['classification']=='feasible_witness':
   (root/'results'/f"witness-{r['spec']['seed']}-{o['id']}.json").write_text(json.dumps(dict(row=row,request=req['request']),indent=2))
  row.pop('points',None);rows.append(row)
 print(file.stem,'classified',len(rows),flush=True)
out=dict(total=len(rows),counts={k:sum(x['classification']==k for x in rows) for k in sorted({x['classification'] for x in rows})},rows=rows)
(root/'results/random-triage.json').write_text(json.dumps(out,indent=2));print(json.dumps(out['counts']))
