import sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.continuity import connection_geometry,lane_rank_error
s=get_scene(7);groups={}
for n in s.nodes.values():
 if n.kind=='lane':groups.setdefault(n.lane_group,[]).append(n)
for key in ['L63423','L67151','L67751']:
 n=s.nodes[key];print('\nSOURCE',key,'index',n.lane_index,'group_count',len(groups[n.lane_group]),'chosen',s.forward[key],flush=True)
 for mid,rel in s.edges.get(key,{}).items():
  if rel!='forward':continue
  for target,r in s.edges.get(mid,{}).items():
   if r!='forward':continue
   dest=s.nodes[target];turn,lateral=connection_geometry(n,dest)
   print(mid,target,'index',dest.lane_index,'count',len(groups.get(dest.lane_group,[])),'deg',round(math.degrees(turn),1),'lat',round(lateral,2),'rank',lane_rank_error(n,dest,groups),flush=True)
   if abs(turn)<math.radians(30):
    print('outgoing offsets',[(x.key,x.lane_index,round(connection_geometry(n,x)[1],2)) for x in groups[dest.lane_group]],flush=True)
