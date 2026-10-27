import sys,math
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.geometry import heading,angle_diff
from engine.continuity import connection_geometry,straight_rank_error
from engine.junctions import connector_curve
s=get_scene(5);key,start=s.locate({'xy':[0,0],'heading':0});n=s.nodes[key]
for target in s.nodes.values():
 if target.kind!='lane':continue
 d=np.linalg.norm(np.asarray(target.baseline.coords[0])[:2]-np.asarray(n.baseline.coords[-1])[:2])
 if d>85:continue
 a,l=connection_geometry(n,target)
 rank=straight_rank_error(n,target,s.graph.lane_groups,s.nodes,s.edges)
 if abs(a)<math.radians(30):
  print(target.key,'d',d,'angle',math.degrees(a),'offset',l,'rank',rank,'start',target.baseline.coords[0], 'CURVE',connector_curve(n,target,s.graph.surface,rank==0) is not None,flush=True)
