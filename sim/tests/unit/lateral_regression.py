"""Recorded failure plus paired-lane checks across real segment boundaries."""
import json,sys,math
from pathlib import Path
import numpy as np
from shapely.geometry import Point
sys.path.insert(0,str(Path(__file__).parents[2]))
from engine.scene import get_scene
from engine.planner import plan,stage
from engine.geometry import arc,tangent,angle_diff
out=Path(__file__).parents[1]/'results'
fixture=json.loads((out/'user-left-fixture.json').read_text())['request']
scene=get_scene(1)
result=plan(fixture)
assert result['status']=='ready',result
assert result['maneuver_start_m']==0,result
assert result['route']['lane_change']['target_corridor']=='C69442',result['route']['lane_change']
assert result['route']['lane_change']['lane_delta']==-1
(out/'user-left-fixed.json').write_text(json.dumps(result,indent=2))
cases=[]
for key,action,target in [('C69505','lane_change_left','C69442'),('C69442','lane_change_right','C69505')]:
 line=scene.nodes[key].baseline
 for s in [.2,5,20,40,60]:
  p=list(line.interpolate(s).coords[0]); h=tangent(line,p)
  req={'scene':1,'state':dict(xy=p,heading=h,node_id=key,speed=20/3.6),'stage':stage(action)}
  r=plan(req)
  assert r['status']=='ready',(key,s,r.get('diagnostics'))
  assert r['maneuver_start_m']==0
  proof=r['route']['lane_change']
  assert proof['target_corridor']==target,proof
  assert abs(proof['lane_delta'])==1,proof
  assert proof['lateral_start_m']*proof['lateral_end_m']>0,proof
  cases.append(dict(source=key,s=s,action=action,target=target,status=r['status']))
# The third connector exits two lanes left. It must not replace a one-lane change.
assert 'C69739' not in scene.topology.lateral_options('C69505',stage('lane_change_left'))
# At the original scene start, left candidates merge back into our same exit.
# Preserve the human-reviewed keep-lane behavior, not a left-then-right detour.
initial=plan({'scene':1,'state':dict(xy=[0,0],heading=0,speed=0),'stage':stage('lane_change_left')})
assert initial['status']=='waiting',initial.get('route_source')
# Connector adjacency must be reciprocal and retain one-lane exit correspondence.
pair_counts=[]
for number in range(1,8):
 sc=get_scene(number);count=0
 for key in sc.topology.by_connector:
  for action,opposite,delta in [('lane_change_left','lane_change_right',-1),('lane_change_right','lane_change_left',1)]:
   for target in sc.topology.lateral_options(key,stage(action)):
    assert key in sc.topology.lateral_options(target,stage(opposite)),(number,key,target)
    a=sc.topology.by_connector[key];b=sc.topology.by_connector[target]
    assert sc.nodes[b.target].lane_index-sc.nodes[a.target].lane_index==delta
    assert sc.nodes[a.target].lane_group==sc.nodes[b.target].lane_group
    count+=1
 pair_counts.append(dict(scene=number,directed_adjacent_pairs=count))
 print('scene',number,'reciprocal pairs',count,flush=True)
report=dict(passed=True,recorded_request=fixture['state']['xy'],position_cases=cases,pair_counts=pair_counts)
(out/'lateral-regression.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
