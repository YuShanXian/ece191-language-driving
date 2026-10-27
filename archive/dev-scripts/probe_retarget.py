import sys,json,pickle,math
from pathlib import Path
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parents[1]/'sim'))
from shapely.geometry import Point,LineString
from engine.geometry import RoadNode,tangent
from engine.junctions import connector_curve
scene=pickle.loads((root/'results/scene1.pkl').read_bytes())
req=json.loads((root/'results/cancel-right-failed.json').read_text())['request'];state=req['state']
key,s=scene.locate(state);old=scene.topology.by_connector[key]
print('state',state['xy'],state['heading'],'located',key,s,old)
p=state['xy'];h=state['heading'];virtual=RoadNode('live',scene.graph.surface,LineString([[p[0]-math.cos(h),p[1]-math.sin(h)],p]),'lane')
for m in scene.topology.by_lane[old.source]:
 n=scene.nodes[m.connector];line=n.baseline;at=line.project(Point(p))
 print(m,'projection',at,line.distance(Point(p)),'heading',tangent(line,line.interpolate(at)),flush=True)
 c=connector_curve(virtual,scene.nodes[m.target],scene.graph.surface,True)
 print('curve',None if c is None else c.length,flush=True)
