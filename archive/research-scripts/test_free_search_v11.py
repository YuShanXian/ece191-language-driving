import json,math
from types import SimpleNamespace
import numpy as np
from shapely.geometry import LineString
import free_navigation_v8 as mod
from mtr_project.paths import ROOT
original=mod.context
stage=lambda a:{'action':a,'source_clause':a,'travel_distance_m':None,'stop_at_end':False}
state={'xy':[0.,0.],'heading':0.,'speed':0.,'view_bounds':[-60,60,-60,60]}
results=[]
for name,action,coords,expected in [
 ('right disconnected visible','turn_right',[(40,-10),(40,-60)],True),
 ('straight disconnected visible','go_straight',[(40,0),(90,0)],True),
 ('left disconnected visible','turn_left',[(40,10),(40,60)],True),
 ('right off screen','turn_right',[(90,-10),(90,-60)],False),
 ('straight no road','go_straight',[],False),
 ('right only left road','turn_right',[(40,10),(40,60)],False),
]:
 nodes={'test':SimpleNamespace(kind='lane',key='test',baseline=LineString(coords))} if coords else {}
 graph=SimpleNamespace(nodes=nodes,edges={});mod.context=lambda scene:(graph,np.zeros(9),np.eye(2))
 r=mod.recover(7,stage(action),state);passed=(r['status']=='completed_offline')==expected
 if expected:passed=passed and nodes['test'].baseline.distance(__import__('shapely').geometry.Point(r['points'][-1]))<.1
 results.append({'case':name,'passed':bool(passed),'status':r['status']})
mod.context=original
from execute_language_plan_v4 import execute
raw=ROOT/'runs/project-v3/provider-benchmark-20261020/raw/f9624d8f-52bf-4e5b-9ed2-387b3941e5e3'
template=json.loads((raw/'parsed.json').read_text())['stages'][0]
poses=[{'xy':[0,0],'heading':0,'speed':0},json.loads((raw/'start-state.json').read_text())]
out=ROOT/'runs/project-v3/free-road-search-v11';out.mkdir(exist_ok=True)
for i,state in enumerate(poses):
 x,y=state['xy'];state['view_bounds']=[x-60,x+60,y-45,y+45]
 for action in ('turn_right','go_straight','turn_left'):
  st={**template,**stage(action),'trigger':'now','target_text':'','constraints':[],'completion_text':''}
  r=execute(7,{'status':'parsed','stages':[st],'unresolved_text':[]},state,mode='free')
  ok=np.isfinite(r['points']).all() and np.linalg.norm(np.array(r['points'][0])-state['xy'])<.01
  if r['status']=='completed_offline':ok=ok and bool(r['stages'][0].get('target'))
  else:ok=ok and 'No road in the visible map' in str(r)
  results.append({'case':str(i)+' '+action,'passed':bool(ok),'status':r['status'],'target':r['stages'][0].get('target')})
  (out/(str(i)+'-'+action+'.json')).write_text(json.dumps(r))
  print(results[-1],flush=True)
(out/'tests.json').write_text(json.dumps(results,indent=2));print(results,flush=True)
assert all(r['passed'] for r in results)
