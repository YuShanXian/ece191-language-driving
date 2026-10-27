import sys,json,pickle,math
from pathlib import Path
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parents[1]/'sim'))
from engine.geometry import tangent,angle_diff
from shapely.geometry import Point
s=pickle.loads((root/'results/scene1.pkl').read_bytes())
for name in ('user-step7-first','user-step7-failed','user-step8-failed'):
 f=json.loads((root/'results'/f'{name}.json').read_text());st=f['request']['state'];key,offset=s.locate(st);n=s.nodes[key]
 print(name,{k:v for k,v in st.items() if k!='history'},'length',n.baseline.length,'offset',offset,'edges',s.edges.get(key),'lane_group',n.lane_group,'index',n.lane_index,'diagnostics',f['result'].get('diagnostics'),flush=True)
 nearby=[]
 for i in s.tree.query(Point(st['xy']).buffer(35),predicate='intersects'):
  k=s.keys[int(i)];node=s.nodes[k];at=node.baseline.project(Point(st['xy']));p=node.baseline.interpolate(at);h=tangent(node.baseline,p)
  nearby.append((round(node.baseline.distance(Point(st['xy'])),2),k,round(math.degrees(angle_diff(h,st['heading'])),1),node.kind,node.lane_group,node.lane_index,list(p.coords[0]),round(node.baseline.length-at,2)))
 print('nearby',sorted(nearby)[:24],flush=True)
