import sys,json,math
from pathlib import Path
import numpy as np
sys.path.insert(0,'historical-project/scripts')
from reverse_motion_v13 import execute_reverse
from execute_language_plan_v4 import execute
r=Path('historical-project');results=[]
base={'trigger':'now','constraints':[],'target_text':'','completion_text':'','source_clause':'test','stop_at_end':True}
for length in (1,5,10,30,100,200):
 s={'xy':[100.,0.],'heading':0.,'speed':0.,'history':[[float(x),0.] for x in range(101)]}
 e=execute_reverse(7,{**base,'action':'reverse','travel_distance_m':length},s)
 actual=e['stages'][0]['traveled_distance_m'];assert abs(actual-min(length,100))<1e-6;assert abs(e['points'][-1][0]-(100-min(length,100)))<1e-6;assert all(abs(math.sin(h))<1e-6 and math.cos(h)>.99 for h in e['heading_rad']);assert e['speed_mps'][-1]==0
 results.append({'test':'reverse '+str(length)+'m','passed':True,'actual_m':actual})
s={'xy':[100.,0.],'heading':0.,'speed':0.,'history':[[float(x),0.] for x in range(101)]}
p={'status':'parsed','unresolved_text':[],'stages':[{**base,'action':'reverse','travel_distance_m':5},{**base,'action':'reverse','trigger':'after_previous','travel_distance_m':5}]}
e=execute(7,p,s,'free');assert abs(e['points'][-1][0]-90)<1e-6;assert len(e['heading_rad'])==len(e['points']);results.append({'test':'two reverses total10m, heading retained','passed':True})
for action in ['stop','hold_stopped','emergency_stop','cancel']:
 p={'status':'parsed','unresolved_text':[],'stages':[{**base,'action':'reverse','travel_distance_m':5},{**base,'action':action,'trigger':'after_previous'}]}
 e=execute(7,p,s,'free');assert e['status']=='completed_offline';assert abs(e['points'][-1][0]-95)<1e-6;results.append({'test':'reverse then '+action+' has no extra movement','passed':True})
(r/'runs/project-v3/basic-commands-v14/motion-tests.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
