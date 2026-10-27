import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,'historical-project/scripts')
from navigation_turn_v15 import execute_turn,road_available
from free_navigation_v8 import recover,context
r=Path('historical-project');out=[]
for scene in range(1,8):
 for action in ['turn_left','turn_right']:
  st={'action':action,'source_clause':action,'trigger':'now','constraints':[],'target_text':'','completion_text':'','travel_distance_m':None};state={'xy':[0,0],'heading':0,'speed':3};e=execute_turn(scene,st,state);row={'scene':scene,'action':action,'status':e['status'],'details':e['stages'][0]}
  if e['status']=='completed_offline':
   g,_,_=context(scene);keys=e['stages'][0]['path'];assert all(g.edges[a].get(b)=='forward' for a,b in zip(keys[:-1],keys[1:]));assert np.linalg.norm(e['points'][0])<1e-6
  if road_available(scene,state):assert recover(scene,st,state)['status']=='blocked'
  out.append(row);print(scene,action,e['status'],e['stages'][0].get('approach_distance_m'),flush=True)
p=r/'runs/project-v3/navigation-turn-v15';p.mkdir(exist_ok=True);(p/'tests.json').write_text(json.dumps(out,indent=2))
