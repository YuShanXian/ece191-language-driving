import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
"""Independently check physical destinations at sub-2-cm label boundaries."""
import sys,json,pickle
from pathlib import Path
from shapely.geometry import Point
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parent))
from engine.geometry import footprint
from fixtures import load_scene
s=load_scene(1)
report=json.loads((root/'results/browser-gate.json').read_text())
cfg=json.loads((root/'results/browser-run-config.json').read_text())['main']
logs=Path(__file__).resolve().parents[3]/'logs'
proof=[]
for line in (logs/'events.jsonl').read_text().splitlines():
 e=json.loads(line)
 if e.get('session_id')!=report['session_id'] or e['type']!='completed':continue
 if not cfg['start']<=e['time']<=cfg['end']:continue
 expected=e['execution']['expected_finish'];actual=e['state']
 if actual.get('node_id')==expected.get('node_id'):continue
 node=s.nodes[expected['node_id']];point=Point(actual['xy'])
 distance=node.baseline.distance(point)
 print(e['action'],expected['node_id'],'baseline',distance,'polygon',node.polygon.distance(point),
       'body_surface',s.graph.surface.covers(footprint(actual['xy'],actual['heading'],4.8,2)),flush=True)
 assert distance<.02
 if e['action'].startswith('lane_change'):
  assert node.polygon.covers(point)
 else:
  # A turn ends on its short destination lane just before the following
  # straight connector. Connector polygons can start after their baseline;
  # verify the requested destination identity and the whole road surface.
  assert s.topology.by_connector[e['route_source']].target==actual['node_id']
 assert s.graph.surface.covers(footprint(actual['xy'],actual['heading'],4.8,2))
 proof.append(dict(action=e['action'],reported_node=actual['node_id'],target_node=expected['node_id'],
  actual_centerline_error_m=distance,full_vehicle_on_road=True))
(root/'results/browser-boundaries.json').write_text(json.dumps(proof,indent=2))
print(json.dumps(proof))
