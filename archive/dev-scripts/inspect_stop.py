import sys,json,pickle,math
from pathlib import Path
from shapely.geometry import Point
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parents[1]/'sim'))
from engine.geometry import tangent,angle_diff
import engine.planner as p
s=pickle.loads((root/'results/scene1.pkl').read_bytes());p.get_scene=lambda _:s
from engine.topology import RoadTopology
s.topology=RoadTopology(s.graph);s.forward=s.topology.forward
events=json.loads((root/'results/user-session.json').read_text())
last=next(e for e in reversed(events) if e['type']=='timed_out')
f=json.loads((root/'results/user-requests'/(last['request_id']+'.json')).read_text())
req=f['request'];state=req['state'];key=state['node_id'];pt=Point(state['xy'])
(root/'results/user-stop-fixture.json').write_text(json.dumps(f))
print('STATE',state['xy'],state['heading'],key,'len',s.nodes[key].baseline.length,'at',s.nodes[key].baseline.project(pt))
print('FORWARD',s.forward.get(key),'EDGES',s.edges.get(key))
print('GROUP',s.nodes[key].lane_group)
for k,n in s.nodes.items():
 if n.kind=='lane' and n.lane_group==s.nodes[key].lane_group:
  print('SAME GROUP',k, 'index',n.lane_index,'moves',s.topology.by_lane.get(k))
for k,relation in s.edges.get(key,{}).items():
 n=s.nodes[k];print(k,relation,'endpoints',list(n.baseline.coords)[::len(n.baseline.coords)-1],
  'angles',math.degrees(tangent(n.baseline,n.baseline.coords[0])),math.degrees(tangent(n.baseline,n.baseline.coords[-1])),
  'topology',s.topology.by_connector.get(k),'outgoing',s.edges.get(k))
for a in ('continuous_drive','go_straight','turn_left','turn_right','u_turn','lane_change_left','lane_change_right'):
 r=p.plan(dict(scene=1,state=state,stage=p.stage(a)));print('ACTION',a,r['status'],r.get('route_source'),r.get('reason'), 'route',r.get('route',{}).get('length') if r.get('route') else None)
