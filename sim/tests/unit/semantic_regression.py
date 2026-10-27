"""Instruction semantics, not merely a valid or moving trajectory."""
import sys,math,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[2]))
from engine.scene import get_scene
from engine.planner import plan,stage
from engine.geometry import heading,angle_diff,arc,validate_path
from engine.intent import validate_intent
out=Path(__file__).parents[1]/'results'
state={'xy':[0,0],'heading':0,'speed':0,'target_speed_mps':20/3.6}
cases=[]
fixture=json.loads((Path(__file__).parents[1]/'fixtures/reverse-one-fixture.json').read_text())
assert not validate_path(fixture['result']['route']['points'])[0], 'The old sub-sample reversal must be rejected'
fixed=plan(fixture['request']);assert fixed['status']=='ready'
p=np.asarray(fixed['route']['points']);delta=p[1]-p[0]
assert abs(angle_diff(math.atan2(delta[1],delta[0])+math.pi,fixture['request']['state']['heading']))<.05
cases.append({'case':'successive reverse has no forward cusp','status':'passed'})
for n in range(1,8):
 s=get_scene(n)
 r=plan({'scene':n,'state':state,'stage':stage('go_straight')})
 assert r['status']=='ready',(n,r.get('reason'))
 assert all(m['action']=='go_straight' or m.get('road_bend') for m in r['route']['movements']),(n,r['route']['movements'])
 if n==1:
  assert r['route_source']=='J_L63477_L67723',r['route_source']
  assert r['route']['movements'][0]['target']=='L67723'
  assert abs(heading(r['route']['points'][:140],True))<math.radians(15)
 if n==5:assert r['route_source']=='J_L67707_L67757'
 cases.append({'scene':n,'action':'go_straight','source':r['route_source'],'status':r['status']})

# Remove only this start lane's straight exits to reproduce the original bug.
# Waiting must stop before the branching junction; left remains reachable.
s=get_scene(1);key,start=s.locate(state)
original=s.topology.by_lane[key];forward=s.forward[key]
try:
 s.topology.by_lane[key]=[m for m in original if m.action!='go_straight']
 s.forward[key]=[]
 r=plan({'scene':1,'state':state,'stage':stage('go_straight')})
 assert r['status']=='waiting'
 assert all(m.get('road_bend') or m['action']=='go_straight' for m in (r.get('route') or {}).get('movements',[]))
 assert r['route']['length']<2.3
 assert plan({'scene':1,'state':state,'stage':stage('turn_left')})['status']=='ready'
 cases.append({'case':'unavailable straight cannot turn left while waiting','status':'passed'})
finally:s.topology.by_lane[key]=original;s.forward[key]=forward

try:
 validate_intent({'movements':[{'action':'turn_left','connector':'wrong'}]},'go_straight')
 raise AssertionError('Unrequested turn accepted')
except ValueError:pass

(out/'semantic-regression.json').write_text(json.dumps(cases,indent=2))
print('semantic regression passed',len(cases),flush=True)
