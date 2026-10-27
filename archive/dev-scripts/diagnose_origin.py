import sys, json, math
from pathlib import Path
import numpy as np
from shapely.geometry import Point
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.continuity import connection_geometry,lane_rank_error
from engine.geometry import heading,angle_diff
from engine.routes import assemble
s=get_scene(1)
key,start=s.locate({'xy':[0,0],'heading':0})
n=s.nodes[key]
print('ORIGIN',key,start,n.baseline.length,n.lane_index,n.lane_group,flush=True)
for k,r in s.edges[key].items():
 print('EDGE',k,r,'exits',s.edges.get(k),flush=True)
 if r=='forward':
  for target in s.edges.get(k,{}):
   a,l=connection_geometry(n,s.nodes[target])
   print('TARGET',target,math.degrees(a),l,flush=True)
   try:
    x=assemble(s,[(key,start,n.baseline.length),(k,0,s.nodes[k].baseline.length),(target,0,min(30,s.nodes[target].baseline.length))],{'xy':[0,0],'heading':0})
    print('SHORT VALID',len(x['points']),flush=True)
   except Exception as e:print('SHORT ERROR',str(e),flush=True)
   try:assemble(s,[(key,start,n.baseline.length),(k,0,s.nodes[k].baseline.length)]+s.continuation(target),{'xy':[0,0],'heading':0});print('TAIL VALID',flush=True)
   except Exception as e:print('TAIL ERROR',str(e),flush=True)
end=np.asarray(n.baseline.coords[-1])[:2]
for target in s.nodes.values():
 if target.kind!='lane' or target.key==key:continue
 p=np.asarray(target.baseline.coords[0])[:2]
 if np.linalg.norm(p-end)>90:continue
 a,l=connection_geometry(n,target)
 if abs(a)<math.radians(30) and p[0]>end[0]:
  print('STRAIGHT CANDIDATE',target.key,'idx',target.lane_index,'group',target.lane_group,'start',p.tolist(),'turn',math.degrees(a),'lateral',l,'rank',lane_rank_error(n,target,s.graph.lane_groups),flush=True)
