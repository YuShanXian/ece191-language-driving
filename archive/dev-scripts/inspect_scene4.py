import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.planner import plan,stage
from engine.geometry import angle_diff,tangent
from shapely.geometry import Point
s=get_scene(4);state={'xy':[0,0],'heading':0,'speed':0,'target_speed_mps':20/3.6}
print('located',s.locate(state),flush=True)
for key in sorted(s.nodes,key=lambda k:s.nodes[k].baseline.distance(Point(0,0)))[:6]:
 n=s.nodes[key];print(key,n.kind,n.baseline.distance(Point(0,0)),tangent(n.baseline,[0,0]),n.baseline.length,s.forward[key],flush=True)
for action in ['turn_left','turn_right','go_straight','continuous_drive']:
 r=plan({'scene':4,'state':state,'stage':stage(action)});print(action,{k:v for k,v in r.items() if k!='route'},flush=True)
