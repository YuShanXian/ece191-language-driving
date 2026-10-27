import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.planner import plan
s=get_scene(1)
req=json.loads((Path(__file__).parents[1]/'results/user-left-fixture.json').read_text())['request']
key,start=s.locate(req['state'])
print('LOCATED',key,start,'RESULT',plan(req)['status'],flush=True)
m=s.topology.by_connector[key]
print('CURRENT',m)
for lane in [m.source,m.target]:
 n=s.nodes[lane];print('LANE',lane,n.lane_group,n.lane_index,n.baseline.length)
 for t,r in s.edges[lane].items():
  print(' EDGE',t,r,'MOVEMENT',s.topology.by_connector.get(t))
  if r in ['left','right']:
   for c in s.topology.by_lane.get(t,[]):print(' NEIGHBOR MOVEMENT',c)
print('CORRIDOR',s.continuation(key,start,200))
