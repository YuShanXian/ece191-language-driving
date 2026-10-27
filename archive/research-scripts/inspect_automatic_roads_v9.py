import json,numpy as np
from mtr_project.paths import ROOT
from evaluate_candidate_checks import load_graph
from shapely.geometry import Point
from trajectory_checks import tangent,angle_diff
manifest=json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text())
for w in manifest:
 c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);center=np.load(ROOT/'runs'/w['run']/'internal_0000.npz')['center'];h=center[6];p=Point(center[:2]);print('SCENE',w['scene'])
 for k,n in g.nodes.items():
  if n.kind=='lane' and n.baseline.distance(p)<7:
   print(k,'index',n.lane_index,'group',n.lane_group)
   for nk,r in g.edges.get(k,{}).items():
    if r=='forward':
     print(' ',nk,[(a,g.nodes[a].lane_index) for a,v in g.edges.get(nk,{}).items() if v=='forward'])
