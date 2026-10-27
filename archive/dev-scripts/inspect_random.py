import json
from pathlib import Path
root=Path(__file__).parents[1]
for file in sorted((root/'results/random').glob('*.json')):
 r=json.loads(file.read_text())
 for o in r['outcomes']:
  if o['status'] not in ('timed_out','error','approaching','executing'):continue
  req=next((x for x in reversed(r['requests']) if str(x['id'])==o.get('request_id')),None)
  if not req:continue
  s=req['request']['state'];d=(req['response'].get('diagnostics') or {})
  print(r['spec']['seed'],r['spec']['scene'],o['action'],o['status'],s.get('node_id'),[round(x,1) for x in s['xy']],round(s['heading'],2),req['response']['status'],d.get('candidate_count'),d.get('rejections',[])[:1])
