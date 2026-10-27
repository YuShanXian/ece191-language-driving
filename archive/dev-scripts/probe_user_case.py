import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
import numpy as np
from engine.scene import get_scene
from engine.planner import plan,stage
from engine.geometry import arc,heading,angle_diff
from engine.routes import assemble
scene=get_scene(1)
state={'xy':[139.53,1802.39],'heading':1.48,'speed':20/3.6,'target_speed_mps':20/3.6}
reports=[]
for action in ('go_straight','lane_change_left','turn_left'):
 result=plan({'scene':1,'state':state,'stage':stage(action)})
 print(action,result['status'],result.get('reason'),scene.locate(state),flush=True)
 reports.append({'state':state,'result':result})
 if result['status']!='ready':break
 p=np.array(result['route']['points']);s=arc(p);distance=result['completion_m'];i=min(len(p)-2,int(np.searchsorted(s,distance)));d=p[i+1]-p[i]
 state={**state,'xy':p[i].tolist(),'heading':math.atan2(d[1],d[0]),'history':p[:i+1].tolist()}
 state['node_id']=next((x['node_id'] for x in result['route']['segments'] if x['start']<=distance<x['end']),None)
key,start=scene.locate(state)
for k,s,e in scene.continuation(key,start,200):
 node=scene.nodes[k]
 if node.kind!='lane':continue
 for connector,rel in scene.edges.get(k,{}).items():
  if rel!='forward':continue
  change=math.degrees(angle_diff(heading(scene.points[connector],True),heading(scene.points[connector])))
  if change<30:continue
  target=next(iter(scene.edges[connector]))
  print('candidate',k,connector,target,round(change,1),flush=True)
  lead=[]
  for section in scene.continuation(key,start,200):
   lead.append(section)
   if section[0]==k:break
  try:assemble(scene,lead+[(connector,0,scene.nodes[connector].baseline.length)]+scene.continuation(target),state);print('valid')
  except Exception as ex:print('invalid',ex,flush=True)
(Path(__file__).parents[1]/'results/user-case-probe.json').write_text(json.dumps(reports,indent=2))
