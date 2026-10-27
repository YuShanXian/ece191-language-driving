import sys,json,math
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[2]))
from engine.planner import plan,stage
from engine.geometry import arc
state={'xy':[0,0],'heading':0,'speed':0,'target_speed_mps':20/3.6}
actions=['go_straight','lane_change_right','lane_change_left','turn_right','go_straight','turn_left','go_straight','turn_left','go_straight']
rows=[]
for a in actions:
 r=plan({'scene':1,'state':state,'stage':stage(a)})
 print('SEQUENCE',a,r['status'],r.get('route_source'),r.get('maneuver_start_m'),r.get('completion_m'),flush=True)
 if r['status']!='ready':
  for alt in ['turn_left','turn_right','go_straight','lane_change_left','lane_change_right']:
   q=plan({'scene':1,'state':state,'stage':stage(alt)});print('ALTERNATIVE',alt,q['status'],q.get('completion_m'),flush=True)
  break
 p=np.asarray(r['route']['points']);s=arc(p);d=r['completion_m']+.1;d=min(d,s[-1]-.02)
 xy=[float(np.interp(d,s,p[:,j])) for j in range(2)]
 i=max(0,min(len(p)-2,int(np.searchsorted(s,d))-1));delta=p[i+1]-p[i]
 node=next((x['node_id'] for x in r['route']['segments'] if x['start']<=d<x['end']),None)
 rows.append({'action':a,'route_source':r['route_source'],'begin':r['maneuver_start_m'],'completion':r['completion_m'],'destination':xy,'route':r['route']})
 state={**state,'xy':xy,'heading':float(math.atan2(delta[1],delta[0])),'node_id':node,'speed':20/3.6}
(Path(__file__).parents[1]/'results/sequence-preview.json').write_text(json.dumps(rows))
