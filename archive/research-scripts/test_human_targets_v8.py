import json,hashlib,numpy as np
from shapely.geometry import Polygon,LineString
from trajectory_checks import RoadNode,RoadGraph
from human_target_match import target_match
from evaluate_candidate_checks import load_graph
from mtr_project.paths import ROOT,write_json
from select_review_instruction import resolve
out=ROOT/'runs/project-v3/human-target-v8';data=json.loads((out/'results.json').read_text());audit=json.loads((out/'selection-audit.json').read_text());assert len(audit)==35
validated=0
for w in data['windows']:
 src=w['source_window'];run=ROOT/'runs'/src['run'];conv=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());g=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);center=np.load(run/'internal_0000.npz')['center'];paths=np.load(out/f'scene-{w["scene"]:02d}-selected.npz')
 for j,ch in enumerate(w['choices']):
  p=paths[f'command_{j}'];assert target_match(p,float(center[6]),g,ch['human_target_roads'])['matched'];assert len(ch['tracking']['cases'])==3
  for angle in [-3,0,3]:
   arr=np.load(out/f'scene-{w["scene"]:02d}-command-{j}-steer{angle:+d}.npz');assert target_match(arr['center_xy'][::4],float(center[6]),g,ch['human_target_roads'])['matched'];validated+=1
  assert (out/f'scene-{w["scene"]:02d}-command-{j}.png').stat().st_size>10000
  assert resolve(w['scene'],ch['instruction'],policy='human_targets')['status']=='road_target_output'
g=RoadGraph([RoadNode('lane',Polygon([(0,-1.75),(60,-1.75),(60,1.75),(0,1.75)]),LineString([(0,0),(60,0)]),'lane')],{})
assert target_match(np.c_[np.linspace(1,40,61),np.zeros(61)],0,g,['lane'])['matched']
assert not target_match(np.c_[np.linspace(1,40,61),np.full(61,3.)],0,g,['lane'])['matched']
assert not target_match(np.c_[np.linspace(40,1,61),np.zeros(61)],np.pi,g,['lane'])['matched']
assert not target_match(np.c_[np.linspace(1,40,61),np.linspace(-15,15,61)],0,g,['lane'])['matched']
current=ROOT/'runs/project-v3/instruction-priority-v7/human-review/targets.json';assert hashlib.sha256(current.read_bytes()).hexdigest()==json.loads((out/'comparison-before.json').read_text())['human_targets_sha256']
write_json(out/'verification.json',{'route_target_matches':35,'tracking_target_matches':validated,'plots':35,'text_entry_checks':35,'negative_checks':['parallel_wrong_lane','wrong_direction','crossing_without_following'],'human_targets_unchanged':True,'scope':'Human target inputs; not independent language or safety success.'})
print('Verified 35 route matches, 105 tracking matches, 35 text-entry responses and 3 negative controls; human selections unchanged.')
