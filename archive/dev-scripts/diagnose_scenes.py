import sys,math,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.geometry import heading,angle_diff
from engine.continuity import connection_geometry
for n in range(1,8):
 s=get_scene(n); key,start=s.locate({'xy':[0,0],'heading':0});node=s.nodes[key]
 print('\nSCENE',n,key,'kind',node.kind,'start',start,'length',node.baseline.length,'index',node.lane_index,'group',node.lane_group,flush=True)
 group=s.graph.lane_groups.get(node.lane_group,[node])
 for src in group:
  print('LANE',src.key,'idx',src.lane_index,'remaining',src.baseline.length-src.baseline.project(__import__('shapely').geometry.Point(0,0)),flush=True)
  for m in s.topology.by_lane.get(src.key,[]):
   print('move',m.connector,m.target,m.action,round(math.degrees(m.angle),1),'lat',round(m.lateral,2),'targetidx',s.nodes[m.target].lane_index,'rank',m.rank_error,flush=True)
 if node.kind=='connector':print('CONNECTOR',s.topology.by_connector.get(key),s.edges[key],flush=True)
