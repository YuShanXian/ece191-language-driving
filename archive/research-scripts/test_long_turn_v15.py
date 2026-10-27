import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,'historical-project/scripts')
from free_navigation_v8 import context,recover
from navigation_turn_v15 import execute_turn,road_available
from trajectory_checks import tangent
r=Path('historical-project');g,c,rot=context(7);st={'action':'turn_left','source_clause':'turn left','trigger':'now','constraints':[],'target_text':'','completion_text':'','travel_distance_m':None};found=[]
for n in sorted((n for n in g.nodes.values() if n.kind=='lane' and n.baseline.length>30),key=lambda n:-n.baseline.length)[:20]:
 p=np.array(n.baseline.interpolate(2).coords[0])[:2];state={'xy':((p-c[:2])@rot).tolist(),'heading':float(tangent(n.baseline,p)-c[6]),'speed':3.}
 for action in ['turn_left','turn_right']:
  st['action']=action;e=execute_turn(7,st,state)
  if e['status']=='completed_offline' and e['stages'][0]['approach_distance_m']>20:
   assert road_available(7,state) and recover(7,st,state)['status']=='blocked';found.append({'state':state,'result':e});print(action,e['stages'][0]['approach_distance_m'],e['stages'][0]['path'],flush=True)
 if len(found)>=2:break
assert len(found)>=2
(r/'runs/project-v3/navigation-turn-v15/long-approach.json').write_text(json.dumps(found))
