import sys,json,math
from pathlib import Path
import numpy as np
from shapely.geometry import Point
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.geometry import tangent,angle_diff
from engine.junctions import connector_curve
s=get_scene(1);out=Path(__file__).parents[1]/'results'
for key in ['L67723','L67619']:
 n=s.nodes[key];print('LANE',key, n.lane_group, n.lane_index, list(n.baseline.coords)[-1],flush=True)
 for m in s.topology.by_lane[key]:print('MOVE',m,flush=True)
print('SOUTH LANES',flush=True)
for key,n in s.nodes.items():
 if n.kind=='lane' and n.baseline.distance(Point(112,-25))<55:
  print(key,n.lane_group,n.lane_index,'start',list(n.baseline.coords)[0],'end',list(n.baseline.coords)[-1],flush=True)
# Inspect heading-compatible outgoing lanes reachable by a right connector.
source=s.nodes['L67723'];valid=[]
for key,n in s.nodes.items():
 if n.kind!='lane' or Point(n.baseline.coords[0]).distance(Point(source.baseline.coords[-1]))>85:continue
 a=angle_diff(tangent(n.baseline,n.baseline.coords[0]),tangent(source.baseline,source.baseline.coords[-1]))
 if -2.6<a<-.52:
  curve=connector_curve(source,n,s.graph.surface,True)
  print('RIGHT EXIT',key,'angle',round(a,3),'len',n.baseline.length,'curve',curve.length if curve else None,flush=True)
  if curve:valid.append(key)
print('VALID',valid,flush=True)
# Save full geometry once for further local geometric experiments, without reloading the map.
import pickle
with (out/'scene1.pkl').open('wb') as f:pickle.dump(s,f)
