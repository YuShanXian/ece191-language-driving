import sys,json,time,contextlib
from functools import lru_cache
import numpy as np
import free_navigation_v8,execute_language_plan_v3,follow_road_v5,evaluate_candidate_checks
from navigation_map_v23 import load_graph as original
@lru_cache(10)
def cached(origin,epsg,path):return original(np.asarray(origin),epsg,path)
def load(origin,epsg,path=None):return cached(tuple(origin),epsg,str(path) if path else None)
for m in (free_navigation_v8,execute_language_plan_v3,follow_road_v5,evaluate_candidate_checks):
 if hasattr(m,'load_graph'):m.load_graph=load
free_navigation_v8.context=lru_cache(8)(free_navigation_v8.context)
from execute_language_plan_v4 import execute
from queued_navigation_v21 import plan_stage,validate_contract
from navigation_contract_v10 import normalize
# Preload the default scene before the first click.
with contextlib.redirect_stdout(sys.stderr):free_navigation_v8.context(7)
for line in sys.stdin:
 try:
  req=json.loads(line);start=time.perf_counter()
  if req.get('op')=='prepare':
   from mtr_project.paths import ROOT
   schema=json.loads((ROOT/'config/language-parser-v4/schema.json').read_text())
   validate_contract(req['plan'],schema)
   plan=normalize(req['plan'])
   print(json.dumps({'id':req['id'],'result':plan}),flush=True);continue
  if req.get('op')=='queue':
   from mtr_project.paths import ROOT
   schema=json.loads((ROOT/'config/language-parser-v4/schema.json').read_text())['properties']['stages']['items']
   schema['properties']['speed_delta_mps']={'type':'number','minimum':0,'maximum':15}
   validate_contract(req['stage'],schema)
   with contextlib.redirect_stdout(sys.stderr):
    result=plan_stage(req['scene'],req['stage'],req['state'],req.get('remaining',20),req.get('elapsed',0),req.get('mode','free'),req.get('next_action'))
   print(json.dumps({'id':req['id'],'result':result}),flush=True);continue
  stage=dict(action=req['action'],source_clause=req['action'].replace('_',' '),trigger='now',trigger_text='',trigger_value=None,target_text='',lane_reference='rightmost' if req['action']=='pull_over' else 'none',lane_number=None,completion_text='',constraints=[],travel_distance_m=10 if req['action']=='reverse' else None,stop_at_end=req['action'] in ('reverse','pull_over'),target_speed_mps=None)
  plan={'status':'parsed','stages':[stage],'unresolved_text':[],'explanation':'Direct command: '+stage['source_clause']+'. No language model used.'}
  with contextlib.redirect_stdout(sys.stderr):plan['execution']=execute(req['scene'],plan,req.get('state'),req.get('mode','free'))
  plan['model_info']={'id':'direct','parser_seconds':0,'planner_seconds':time.perf_counter()-start}
  print(json.dumps({'id':req['id'],'result':plan}),flush=True)
 except Exception as e:print(json.dumps({'id':req.get('id'),'error':str(e)}),flush=True)
