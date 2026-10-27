import json,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.planner import plan,stage
from engine.geometry import tangent,heading
from engine.routes import turn
from engine.lane_changes import lane_change
out=Path(__file__).parents[1]/'results'
s=get_scene(1);req=json.loads((out/'turn_left-watched.json').read_text())['request']
print('WATCHED',req['state']['xy'],s.locate(req['state']))
for lane in s.graph.lane_groups[s.nodes['L63435'].lane_group]:
 print('ENTRY',lane.key,lane.lane_index)
 for m in s.topology.by_lane.get(lane.key,[]):print('MOVE',m)
for a in ['lane_change_left','lane_change_right']:
 r=plan({**req,'stage':stage(a)})
 print('PREP',a,r['status'],r.get('route_source'),r.get('completion_m'),r.get('reason'))
 if r['status']=='ready':(out/(a+'-prep.json')).write_text(json.dumps(r,indent=2))
metadata={key:dict(kind=n.kind,group=n.lane_group,rank=n.lane_index,length=n.baseline.length,points=list(n.baseline.coords),edges=s.edges.get(key,{})) for key,n in s.nodes.items()}
(out/'scene1-node-reference.json').write_text(json.dumps(metadata))
