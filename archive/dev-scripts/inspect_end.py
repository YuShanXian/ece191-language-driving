import sys,json,math
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.planner import plan,stage
from engine.routes import assemble
from engine.geometry import arc
s=get_scene(1)
for key in ['L67838','L67777']:
 n=s.nodes[key]
 print('END',key,n.baseline.length,s.edges.get(key),flush=True)
 print('OPTIONS',s.topology.by_lane.get(key),flush=True)
 for m in s.topology.by_lane.get(key,[]):
  try:
   r=assemble(s,[(key,0,n.baseline.length),(m.connector,0,s.nodes[m.connector].baseline.length),(m.target,0,min(8,s.nodes[m.target].baseline.length))])
   print('valid',m.connector,flush=True)
  except ValueError as e:print('invalid',m.connector,str(e),flush=True)
source=json.loads((Path(__file__).parents[1]/'results/sequence-preview.json').read_text())[0]
p=np.array(source['route']['points']);a=arc(p);d=source['completion']+.1;i=np.searchsorted(a,d)-1;delta=p[i+1]-p[i]
state={'xy':[np.interp(d,a,p[:,j]) for j in range(2)],'heading':math.atan2(delta[1],delta[0]),'speed':20/3.6,'target_speed_mps':20/3.6,'node_id':'L67723'}
for action in ['turn_left','turn_right','go_straight','lane_change_left','lane_change_right']:
 r=plan({'scene':1,'state':state,'stage':stage(action)});print('AFTER FIRST',action,r['status'],r.get('route_source'),r.get('maneuver_start_m'),flush=True)
