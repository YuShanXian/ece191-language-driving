import sys, json, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from fixtures import load_scene
from engine.geometry import tangent
s=load_scene(1)
keys=['L67605','L67619','L67723','L68098','L63477']
if len(sys.argv)>1: keys=sys.argv[1:]
for key in keys:
 n=s.nodes[key]
 print('\nNODE',key,'group',n.lane_group,'rank',n.lane_index,'length',n.baseline.length,'start/end',list(n.baseline.coords)[::max(1,len(n.baseline.coords)-1)])
 print('group',[(x.key,x.lane_index) for x in s.graph.lane_groups[n.lane_group]])
 print('forward',s.topology.forward[key])
 for lane in s.graph.lane_groups[n.lane_group]:
  print(' lane',lane.key)
  for m in s.topology.by_lane.get(lane.key,[]):
   end=s.nodes[m.target]; conn=s.nodes[m.connector]
   print(m,'exit_group',end.lane_group,'exit_rank',end.lane_index,'connector_length',conn.baseline.length,'target_length',end.baseline.length)
   print(' headings',*[round(math.degrees(tangent(x.baseline,p)),2) for x,p in [(lane,lane.baseline.coords[-1]),(conn,conn.baseline.coords[0]),(conn,conn.baseline.coords[-1]),(end,end.baseline.coords[0])]])
