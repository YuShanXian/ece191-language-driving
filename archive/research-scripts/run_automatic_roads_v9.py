"""Generate automatic predictions BEFORE opening any human label file."""
import json,hashlib,numpy as np
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph
from automatic_road_selector import select_road
out=ROOT/'runs/project-v3/automatic-road-v9';out.mkdir(exist_ok=True)
# Frozen, minimal scene inventory: only scene number and source file paths.
manifest=json.loads((out/'input-manifest.json').read_text())
commands=['Go straight','Turn left','Turn right','Change lanes to the left','Change lanes to the right']
rows=[]
for w in manifest:
 c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);center=np.load(ROOT/'runs'/w['run']/'internal_0000.npz')['center']
 for j,text in enumerate(commands):
  result=select_road(g,center,text);rows.append({'scene':w['scene'],'command':j,'instruction':text,**result});print(w['scene'],j,result.get('reason'),result.get('selected',{}).get('target'),flush=True)
write_json(out/'predictions.json',{'scope':'Map/state/text-only road predictions. Human labels not read by selector. Seven development scenes, not held-out validation.','rows':rows,'selector_sha256':hashlib.sha256((ROOT/'scripts/automatic_road_selector.py').read_bytes()).hexdigest()})
