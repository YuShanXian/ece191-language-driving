"""Physical and semantic checks on the two exact recorded failures."""
import sys,json,pickle,math
from pathlib import Path
import numpy as np
from shapely.geometry import LineString,box
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parent))
from engine.geometry import footprint,arc
from engine.recovery import reverse_clearance
from fixtures import load_scene
s=load_scene(1)
right=json.loads((root/'results/turn_right-fixed.json').read_text())
assert right['route_source']=='C70254'
proof=right['route']['preparation'];assert proof['lane_delta']==1
assert proof['end']<right['maneuver_start_m']
turns=[m for m in right['route']['movements'] if m['action']!='go_straight' and not m.get('road_bend')]
assert len(turns)==1 and turns[0]['connector']=='C70254'
u=json.loads((root/'results/u_turn-fixed.json').read_text())
back,forward=u['phases'];assert back['route']['reverse'] and back['stop_at_end']
assert reverse_clearance(back['route'],s.graph.surface)
assert not reverse_clearance(back['route'],box(0,0,5,5)),'fabricated off-road history accepted'
p=np.asarray(forward['route']['points']);d=arc(p)
turn_end=next(m['end'] for m in forward['route']['movements'] if m['connector'].startswith('RECOVERY_'))
p=p[d<=turn_end];v=np.gradient(p,axis=0);h=np.arctan2(v[:,1],v[:,0])
assert all(s.graph.surface.covers(footprint(x,a,4.8,2)) for x,a in zip(p,h))
assert u['recovery']['max_curvature']<=.215
assert np.linalg.norm(np.asarray(back['route']['points'][-1])-forward['route']['points'][0])<.001
assert u['recovery']['target_node'] in s.nodes
result=dict(passed=True,native_right='C70254',preparatory_lanes=1,reverse_m=u['recovery']['reverse_m'],
 target_lane=u['recovery']['target_node'],u_turn_minimum_radius_m=1/u['recovery']['max_curvature'],
 full_vehicle_footprint=[4.8,2],forward_footprint_samples=len(p))
(root/'results/failure-geometry.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
