import json
from mtr_project.paths import ROOT,write_json
out=ROOT/'runs/project-v3/automatic-road-v9';pred=json.loads((out/'predictions.json').read_text());human=json.loads((ROOT/'runs/project-v3/instruction-priority-v7/human-review/targets.json').read_text());labels={(r['scene'],r['command']):r for r in human['reviews']};rows=[]
for r in pred['rows']:
 wanted=labels[r['scene'],r['command']]['road_ids'];selected=r.get('selected',{});hit=bool(set(wanted)&set(selected.get('path',[])));rows.append({'scene':r['scene'],'command':r['command'],'instruction':r['instruction'],'human_roads':wanted,'automatic_road':selected.get('target'),'path_id_match':hit,'reason':r.get('reason')})
 if not hit:
  print('\nMISMATCH',r['scene'],r['command'],'wanted',wanted,'got',selected)
  print('APPROACHES',r.get('approaches'))
  print('LABEL BRANCHES',[b for b in r.get('branches',[]) if set(wanted)&set(b['path'])])
write_json(out/'road-evaluation.json',{'matched':sum(r['path_id_match'] for r in rows),'total':len(rows),'definition':'Selected graph path includes at least one human alternative road ID. Not trajectory or safety success.','rows':rows})
print('MATCHED',sum(r['path_id_match'] for r in rows),'/',len(rows))
