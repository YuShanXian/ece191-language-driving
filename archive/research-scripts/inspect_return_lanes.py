import json, numpy as np
from shapely.geometry import Point
from free_navigation_v8 import context
from trajectory_checks import tangent,angle_diff
from mtr_project.paths import ROOT
g,initial,rot=context(7)
for ident in ['cf615973-4c9b-447f-a2b4-c182a2141fef','f9624d8f-52bf-4e5b-9ed2-387b3941e5e3']:
 s=json.loads((ROOT/'runs/project-v3/provider-benchmark-20261020/raw'/ident/'start-state.json').read_text());xy=initial[:2]+np.array(s['xy'])@rot.T;h=initial[6]+s['heading'];out=[]
 for n in g.nodes.values():
  if n.kind!='lane':continue
  d=n.baseline.distance(Point(xy));a=abs(angle_diff(tangent(n.baseline,xy),h));station=n.baseline.project(Point(xy))
  if d<80 and a>np.radians(140):out.append({'key':n.key,'distance':round(d,2),'angle':round(float(np.degrees(a)),1),'remaining':round(n.baseline.length-station,2)})
 print(ident,sorted(out,key=lambda x:x['distance'])[:8])
