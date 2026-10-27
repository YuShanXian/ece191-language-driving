import csv,json
from pathlib import Path
from mtr_project.paths import ROOT
manifest=json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text())
rows=list(csv.DictReader((ROOT/'references/release_annotationsV1.csv').open(encoding='utf-8-sig')))
out=[]
for w in manifest:
 c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());clip=c['source_clip'];labels=[r for r in rows if r['clip_id']==clip and r['passenger_instruction'].strip()]
 out.append({'scene':w['scene'],'clip':clip,'timestamp_us':c['current_timestamp_us'],'labels':labels})
base=ROOT/'runs/project-v3/doplan-integration-v1';base.mkdir(exist_ok=True)
(base/'scene-labels.json').write_text(json.dumps({'source':'references/release_annotationsV1.csv','matching':'clip_id only; temporal overlap not yet confirmed','scenes':out},indent=2))
for x in out:
 print('SCENE',x['scene'],x['clip'],'labels',len(x['labels']))
 for r in x['labels']:print(r['annotation_id'],r['start_frame'],r['end_frame'],r['passenger_instruction'])
