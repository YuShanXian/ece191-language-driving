import json,numpy as np,hashlib
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph
from human_target_match import target_match
base=ROOT/'runs/project-v3/instruction-priority-v7';out=ROOT/'runs/project-v3/human-target-v8';out.mkdir(exist_ok=True);data=json.loads((base/'results.json').read_text());targets=json.loads((base/'human-review/targets.json').read_text());rows=[]
for w in data['windows']:
 s=w['scene'];src=w['source_window'];run=ROOT/'runs'/src['run'];c=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);center=np.load(run/'internal_0000.npz')['center'];paths=np.load(base/f'scene-{s:02d}-selected.npz');raw=np.load(run/'refined_v2_candidates.npz')['world_xy']
 for j,ch in enumerate(w['choices']):
  human=targets['reviews'][(s-1)*5+j];wanted=human['road_ids'];match=target_match(paths[f'command_{j}'],float(center[6]),g,wanted) if f'command_{j}' in paths else None
  candidates=[]
  if not match or not match['matched']:
   for i,p in enumerate(raw):
    m=target_match(np.vstack([center[:2],p]),float(center[6]),g,wanted)
    if m['matched']:candidates.append(i+1)
  status='matches_selected_road' if match and match['matched'] else ('no_output' if match is None else 'not_confirmed_on_selected_road')
  row={'scene':s,'command':j,'action':ch['action'],'human_roads':wanted,'before_status':status,'before_match':match,'alternative_mtr_candidates':candidates};rows.append(row);print(s,j,status,'MTR alternatives',candidates,flush=True)
write_json(out/'comparison-before.json',{'rows':rows,'human_targets_sha256':hashlib.sha256((base/'human-review/targets.json').read_bytes()).hexdigest(),'definition':'Geometric alignment with user-selected road alternatives; not driving success or safety.'})
write_json(out/'human-targets-snapshot.json',targets)
