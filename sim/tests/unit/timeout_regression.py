"""Exact recorded failures must produce the correct executable maneuver."""
import sys,json,math
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[2]))
from engine.scene import get_scene
from engine.planner import plan,stage
from engine.geometry import heading,angle_diff,arc
out=Path(__file__).parents[1]/'results'
fixtures=json.loads((out/'timeout-fixtures.json').read_text())
checks=[]
for case in fixtures:
 r=case['request']; result=plan(r); action=r['stage']['action']
 assert result['status']=='ready',(case['id'],result.get('reason'))
 expected='J_L63167_L67444' if action=='turn_left' else 'J_L63435_L67608'
 assert result['route_source']==expected
 s=get_scene(1);curve=s.points[expected]
 degrees=math.degrees(angle_diff(heading(curve,True),heading(curve)))
 assert 60 < degrees < 110 if action=='turn_left' else -110 < degrees < -60
 assert result['completion_m']>result['maneuver_start_m']
 checks.append({'case':case['id'],'action':action,'connector':expected,'angle_deg':degrees,'begin_m':result['maneuver_start_m'],'previous_status':case['result']['status'],'status':result['status']})
print(json.dumps(checks,indent=2),flush=True)
(out/'timeout-regression.json').write_text(json.dumps(checks,indent=2))

# Find a reproducible physically unavailable command for the live timeout gate.
s=get_scene(1)
state={'xy':[0,0],'heading':0,'speed':0,'target_speed_mps':20/3.6}
for a in ['turn_left','lane_change_left','lane_change_right']:
 result=plan({'scene':1,'state':state,'stage':stage(a)})
 print('sequence',a,result['status'],result.get('route_source'),flush=True)
 if result['status']!='ready':break
 p=np.asarray(result['route']['points']);arcs=arc(p);d=result['completion_m'];i=min(len(p)-2,int(np.searchsorted(arcs,d)))
 state={**state,'xy':p[i].tolist(),'heading':heading(p[i:i+2]),'speed':20/3.6,'node_id':next((x['node_id'] for x in result['route']['segments'] if x['start']<=d<x['end']),None)}
 for candidate in ['turn_left','turn_right','lane_change_left','lane_change_right','u_turn']:
  q=plan({'scene':1,'state':state,'stage':stage(candidate)})
  print('next',candidate,q['status'],q.get('maneuver_start_m'),q.get('reason'),flush=True)
