import csv,json,hashlib
from mtr_project.paths import ROOT
base=ROOT/'runs/project-v3/doplan-integration-v1';audit=json.loads((base/'scene-labels.json').read_text());p=ROOT/'runs/project-v3/recording-demo-v1/data.json';data=json.loads(p.read_text())
for scene in audit['scenes']:
 gps=ROOT/'data/doplan'/scene['clip']/'gps.csv';times=[int(r['timestamp_us']) for r in csv.DictReader(gps.open(encoding='utf-8-sig'))] if gps.exists() else []
 frame=min(range(len(times)),key=lambda i:abs(times[i]-scene['timestamp_us'])) if times else None
 scene['nearest_gps_row']=frame;scene['timestamp_residual_s']=abs(times[frame]-scene['timestamp_us'])/1e6 if times else None
 for r in scene['labels']:r['overlaps_scene_under_gps_row_mapping']=frame is not None and int(r['start_frame'])<=frame<int(r['end_frame'])
 scene['labels'].sort(key=lambda r:(not r['overlaps_scene_under_gps_row_mapping'],r['annotation_id']))
 data['scenes'][str(scene['scene'])]['doplan']=scene
 print(scene['scene'],'GPS row',frame,'residual seconds',scene['timestamp_residual_s'],'overlap',sum(r['overlaps_scene_under_gps_row_mapping'] for r in scene['labels']))
audit['matching']='Exact clip_id plus conditional nearest GPS-row interval check; not confirmed instruction issue time.'
audit['source_sha256']=hashlib.sha256((ROOT/'references/release_annotationsV1.csv').read_bytes()).hexdigest()
(base/'scene-labels.json').write_text(json.dumps(audit,indent=2));p.write_text(json.dumps(data))
p=ROOT/'runs/project-v3/recording-demo-v1/index.html';s=p.read_text(encoding='utf-8-sig')
if 'id="doplan"' not in s:
 s=s.replace('<form class="chat"','''<details style="margin-top:14px;border:1px solid #d7e1eb;background:white;border-radius:10px;padding:12px"><summary>Explore original doPlan instructions</summary><p style="font-size:13px;margin:10px 0">Original labels from this video clip. Window overlap uses a conditional GPS mapping, not an instruction execution time. Local inspection only; labels are not sent to the model.</p><select id="doplan" aria-label="doPlan annotation" style="width:100%;padding:8px"></select><p id="labeltext" style="margin:10px 0;color:#152d43"></p><p id="labelmeta" style="font-size:12px"></p></details><form class="chat"''')
 s=s.replace('function switchScene(){', '''function showLabel(){const r=data.doplan.labels[Number($('#doplan').value)];$('#labeltext').textContent=r?r.passenger_instruction:'No original labels found.';$('#labelmeta').textContent=r?r.annotation_id+' · Frames '+r.start_frame+'–'+r.end_frame+' · '+r.referential_label+' · '+(r.overlaps_scene_under_gps_row_mapping?'Window overlap (conditional)':'Other time window in this clip'):''}
$('#doplan').onchange=showLabel;
function switchScene(){''')
 s=s.replace("data=allScenes[$('#scene').value];selected=-1", "data=allScenes[$('#scene').value];$('#doplan').replaceChildren(...data.doplan.labels.map((r,i)=>{const o=document.createElement('option');o.value=i;o.textContent=r.annotation_id+' · '+(r.overlaps_scene_under_gps_row_mapping?'Window overlap':'Other window');return o}));showLabel();selected=-1")
 p.write_text(s)
