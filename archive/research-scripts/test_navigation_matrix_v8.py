import json, math, time
import numpy as np
from mtr_project.paths import ROOT
from execute_language_plan_v4 import execute
OUT=ROOT/'runs/project-v3/navigation-modes-v8';OUT.mkdir(exist_ok=True)
raw=ROOT/'runs/project-v3/provider-benchmark-20261020/raw/f9624d8f-52bf-4e5b-9ed2-387b3941e5e3'
original=json.loads((raw/'parsed.json').read_text());end=json.loads((raw/'start-state.json').read_text())
template=original['stages'][0]
def stage(action,distance=None,stop=False):
 s={**template,'action':action,'source_clause':action,'trigger':'now','travel_distance_m':distance,'stop_at_end':stop,'target_text':'','constraints':[],'completion_text':''};return s
def plan(stages):return {'status':'parsed','stages':stages,'unresolved_text':[],'explanation':'Deterministic navigation regression, no language-model variability.'}
route=json.loads((ROOT/'runs/project-v3/recording-demo-v1/continuous.json').read_text())['7']['path']
poses={'start':{'xy':[0,0],'heading':0,'speed':0},'reported_end':end}
for fraction in (.25,.5,.75):
 i=max(1,int((len(route)-1)*fraction));d=np.asarray(route[i])-route[i-1]
 poses[str(fraction)]={'xy':route[i],'heading':math.atan2(d[1],d[0]),'speed':5.}
actions=[('straight30',[stage('go_straight',30,True)]),('left',[stage('turn_left')]),('right',[stage('turn_right')]),('change_left',[stage('lane_change_left')]),('change_right',[stage('lane_change_right')]),('uturn100',[stage('u_turn'),stage('go_straight',100,True)]),('stop',[stage('stop')])]
results=[]
for name,state in poses.items():
 for action,stages in actions:
  started=time.time()
  try:
   r=execute(7,plan(stages),state,mode='free');p=np.asarray(r['points']);finite=np.isfinite(p).all() and np.isfinite(r['speed_mps']).all();continuity=np.linalg.norm(p[0]-state['xy'])<.001
   ok=(r['status']=='completed_offline' and len(r['stages'])==len(stages) and finite and continuity) or (action=='stop' and r['status']=='live_control' and r.get('commands')==[{'action':'stop','speed_mps':None}])
   if action=='uturn100':
    row=r['stages'][0];i=row['end_point'];d=p[i]-p[max(0,i-3)];angle=abs(math.atan2(math.sin(math.atan2(d[1],d[0])-state['heading']),math.cos(math.atan2(d[1],d[0])-state['heading'])));ok=ok and angle>math.radians(140)
   result={'pose':name,'action':action,'passed':bool(ok),'status':r['status'],'warnings':sum(bool(s.get('warning') or s.get('status')=='geometry_demo_only') for s in r['stages']),'seconds':round(time.time()-started,2)}
   (OUT/(name+'-'+action+'.json')).write_text(json.dumps(r))
  except Exception as e:result={'pose':name,'action':action,'passed':False,'error':str(e)}
  results.append(result);print(json.dumps(result),flush=True);(OUT/'matrix.json').write_text(json.dumps(results,indent=2))
# Consecutive commands: use the previous endpoint, never reset to the scene origin.
state=end
for i in range(3):
 r=execute(7,plan([stage('u_turn'),stage('go_straight',60,True)]),state,mode='free');p=np.asarray(r['points']);d=p[-1]-p[-3]
 ok=r['status']=='completed_offline' and np.linalg.norm(p[0]-state['xy'])<.001
 results.append({'pose':'sequential','action':'uturn60-'+str(i),'passed':bool(ok),'status':r['status']});(OUT/('sequential-'+str(i)+'.json')).write_text(json.dumps(r));print(json.dumps(results[-1]),flush=True)
 state={'xy':p[-1].tolist(),'heading':float(math.atan2(d[1],d[0])),'speed':r['speed_mps'][-1]}
(OUT/'matrix.json').write_text(json.dumps(results,indent=2))
print('TOTAL',sum(r['passed'] for r in results),'/',len(results),flush=True)
