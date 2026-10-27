import sys,time,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.planner import plan,stage
from engine.geometry import arc
from shapely.geometry import Point
import numpy as np
scene=get_scene(1)
state={'xy':[0,0],'heading':0,'speed':0,'target_speed_mps':20/3.6}
r=plan({'scene':1,'state':state,'stage':stage('turn_left')})
p=np.array(r['route']['points']);s=arc(p)
rows=[]
for distance in (90,120,500,1800,1842.8,1880,1900):
 index=min(len(p)-2,int(np.searchsorted(s,distance)));direction=p[index+1]-p[index]
 state={'xy':p[index].tolist(),'heading':math.atan2(direction[1],direction[0]),'speed':20/3.6,'target_speed_mps':20/3.6,'history':p[max(0,index-100):index+1].tolist()}
 located=scene.locate(state);state['node_id']=located[0]
 for action in ('lane_change_left','lane_change_right','turn_left','go_straight','u_turn','reverse'):
  result=plan({'scene':1,'state':state,'stage':stage(action)})
  row={'distance':distance,'node':located[0],'action':action,**{k:v for k,v in result.items() if k!='route'}};rows.append(row)
  print(json.dumps(row),flush=True)
(Path(__file__).parents[1]/'results/sequence-probe.json').write_text(json.dumps(rows,indent=2))
