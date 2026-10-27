import sys,json,math
from pathlib import Path
import numpy as np
from shapely.geometry import Point
r=Path('historical-project');sys.path.insert(0,str(r/'scripts'))
from free_navigation_v8 import context
from navigation_turn_v15 import locate
from trajectory_checks import tangent,angle_diff
g,c,rot=context(7)
for id in ['e66842f5-f490-45d4-900c-6959cc39a48b','f2e4c606-bc1e-4765-85db-b32b6cb1cda3','1d3fd45b-e973-4cb2-b616-bce5db5b4c28']:
 state=json.loads((r/'runs/project-v3/provider-benchmark-20261020/raw'/id/'start-state.json').read_text());p=c[:2]+np.asarray(state['xy'])@rot.T;h=c[6]+state['heading'];key=locate(g,p,h);n=g.nodes[key];line=n.baseline;s=line.project(Point(p));end=np.asarray(line.coords[-1])[:2]
 print(id,key,n.kind,'remaining',line.length-s,'headingchange ahead',math.degrees(angle_diff(tangent(line,end),h)),'edges',g.edges.get(key),flush=True)
 for k,rel in g.edges.get(key,{}).items():
  nn=g.nodes[k];ll=nn.baseline;print(' ',k,rel,nn.kind,'length',ll.length,'change',math.degrees(angle_diff(tangent(ll,np.asarray(ll.coords[-1])[:2]),tangent(ll,np.asarray(ll.coords[0])[:2]))))
