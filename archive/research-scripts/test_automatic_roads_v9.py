import json,builtins,numpy as np
from pathlib import Path
from unittest.mock import patch
from shapely.affinity import rotate,translate
from trajectory_checks import RoadGraph,RoadNode
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph
from automatic_road_selector import select_road
out=ROOT/'runs/project-v3/automatic-road-v9';manifest=json.loads((out/'input-manifest.json').read_text());pred=json.loads((out/'predictions.json').read_text())['rows'];tests=[]
for w in manifest:
 c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);center=np.load(ROOT/'runs'/w['run']/'internal_0000.npz')['center'];theta=.7;rot=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]]);other=center.copy();other[:2]=rot@center[:2]+[101,-37];other[6]+=theta;other[7:9]=rot@center[7:9]
 transform=lambda shape:translate(rotate(shape,theta,origin=(0,0),use_radians=True),101,-37)
 gg=RoadGraph([RoadNode(n.key,transform(n.polygon),transform(n.baseline),n.kind,n.lane_group,n.lane_index) for n in g.nodes.values()],g.edges)
 for row in [r for r in pred if r['scene']==w['scene']]:
  with patch.object(builtins,'open',side_effect=AssertionError('selector attempted file read')),patch.object(Path,'open',side_effect=AssertionError('selector attempted file read')):
   result=select_road(g,center,row['instruction']);moved=select_road(gg,other,row['instruction'])
  assert result['selected']['target']==row['selected']['target']
  assert moved['selected']['target']==result['selected']['target'],(w['scene'],row['command'],moved['selected']['target'])
  tests.append({'scene':row['scene'],'command':row['command'],'no_file_access':True,'rotation_translation_invariant':True})
 assert select_road(g,center,'drive to the coffee shop')['status']=='unsupported_instruction'
write_json(out/'verification.json',{'passed':True,'tests':tests,'unsupported_instruction_tests':7,'note':'Selector cannot read files during tests; global rotation/translation preserves its choices. These are development-scene checks, not unseen-scene accuracy.'});print('35 no-I/O tests, 35 coordinate invariance tests, 7 unsupported-input tests passed')
