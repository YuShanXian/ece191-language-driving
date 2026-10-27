import sys,json,math
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.planner import plan,stage
from engine.geometry import arc,validate_path
s=get_scene(1)
for state in [dict(xy=[0,0],heading=0,speed=0),dict(xy=[50.72,40.26],heading=1.53,speed=20/3.6)]:
 r=plan(dict(scene=1,state=state,stage=stage('turn_right')))
 print('PLAN',state,r['status'],r.get('route_source'),r.get('reason'),flush=True)
 if r['status']!='ready':continue
 route=r['route'];key=s.topology.by_connector[r['route_source']].source
 for lane in s.graph.lane_groups[s.nodes[key].lane_group]:
  print('ENTRY',lane.key,lane.lane_index)
  for m in s.topology.by_lane.get(lane.key,[]):
   if m.action=='turn_right':print('RIGHT',m,'length',s.nodes[m.connector].baseline.length)
 (Path(__file__).parents[1]/'results'/('right-origin.json' if state['xy']==[0,0] else 'right-after-left.json')).write_text(json.dumps({'request':dict(scene=1,state=state,stage=stage('turn_right')),'result':r},indent=2))
