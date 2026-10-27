import sys, json, importlib.util
from pathlib import Path
from dataclasses import asdict
from fixtures import load_scene
from engine import planner
from engine.topology import RoadTopology
from engine.geometry import validate_path, footprint, resample, tangent
from engine.routes import follow
from shapely.geometry import LineString
import numpy as np

root=Path(__file__).parents[1]
planner.get_scene=load_scene
# Fixed regression expectations replace comparison with a copied old app.
changes=[]
assert load_scene(1).forward['L63477']==['J_L63477_L67723']
assert load_scene(1).forward['L68098']==['C64857']
assert load_scene(1).forward['L67605']==['C69782']
s=load_scene(1)
# Removing the actual rejoin must make this a genuine unresolved fork again.
import copy
fork=copy.copy(s.graph);fork.edges={k:dict(v) for k,v in s.edges.items()}
fork.edges['L67625']={k:v for k,v in fork.edges['L67625'].items() if k!='C69923'}
assert RoadTopology(fork).forward['L67605']==[]
checks=[]
for name in ['user-right-request','user-straight-request']:
 archived=json.loads((root/'results'/f'{name}.json').read_text())
 result=planner.plan(archived['request'])
 (root/'results'/f'{name}-fixed.json').write_text(json.dumps(result))
 assert result['status']=='ready',(name,result)
 route=result['route']; ids=[x['node_id'] for x in route['segments']]
 assert 'C69782' in ids and 'L67695' in ids and 'C69338' in ids and 'L67733' in ids,(name,ids)
 assert 'C69753' not in ids and 'C70265' not in ids
 assert validate_path(route['points'])[0]
 # Independently inspect every quarter-meter of the repaired native bend,
 # including the full body against the map's drivable surface.
 native=LineString([p for key in ['C70254','L67605','C69782','L67695','C69338','L67733'] for p in s.nodes[key].baseline.coords])
 points=resample(np.asarray(native.coords),.25)
 outside=max(footprint(p,tangent(native,p),4.8,2).difference(s.graph.surface).area for p in points)
 assert outside<.02,(name,'body leaves map',outside)
 checks.append(dict(request=name,status=result['status'],source=result.get('route_source'),continuation_nodes=ids,full_body_outside_area=outside,route_length=route['length'],completion_m=result['completion_m']))
(root/'results/continuation-geometry.json').write_text(json.dumps(dict(passed=True,topology_changes=changes,requests=checks),indent=2))
print(json.dumps(dict(passed=True,changed_nodes=changes,requests=checks),indent=2))
