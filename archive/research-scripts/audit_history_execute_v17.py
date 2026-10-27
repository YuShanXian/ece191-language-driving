import sys,json,hashlib,time,math
from pathlib import Path
from functools import lru_cache
import numpy as np
r=Path('historical-project');sys.path.insert(0,str(r/'scripts'));out=r/'runs/project-v3/command-audit-v17'
import free_navigation_v8,execute_language_plan_v3,follow_road_v5,evaluate_candidate_checks
free_navigation_v8.context=lru_cache(8)(free_navigation_v8.context)
original=evaluate_candidate_checks.load_graph
@lru_cache(10)
def cached(origin,epsg,path):return original(np.asarray(origin),epsg,path)
def load(origin,epsg,path=None):return cached(tuple(origin),epsg,str(path) if path else None)
for m in (execute_language_plan_v3,follow_road_v5,evaluate_candidate_checks):
 if hasattr(m,'load_graph'):m.load_graph=load
from execute_language_plan_v4 import execute
records=json.loads((out/'inventory.json').read_text());records=[x for x in records if x['state'] is not None];rows=[]
for idx,x in enumerate(records):
 key=hashlib.sha256(x['instruction'].encode()).hexdigest()[:16];p=out/'fresh-parses'/(key+'.json')
 deadline=time.monotonic()+1200
 while not p.exists() and time.monotonic()<deadline:time.sleep(2)
 row={k:x[k] for k in ('path','instruction','scene','old_status')};row['scene_assumed']=x['scene'] is None
 if not p.exists():row.update(status='parser_not_available')
 else:
  fresh=json.loads(p.read_text());plan=fresh.get('parsed');row['parsed_actions']=[s['action'] for s in (plan or {}).get('stages',[])]
  try:
   if plan is None:raise ValueError(fresh.get('error','No parsed response'))
   scene=x['scene'] or 7;e=execute(scene,plan,x['state'],'free');dest=out/'executions';dest.mkdir(exist_ok=True);(dest/(str(idx)+'.json')).write_text(json.dumps(e));row.update(status=e['status'],reason=e.get('reason') or ' / '.join(s.get('reason','') for s in e.get('stages',[])),execution=str(idx)+'.json',lane_changes=[c for s in e.get('stages',[]) for c in s.get('preparatory_lane_changes',[])])
   if e['status']=='completed_offline':
    pp=np.asarray(e['points']);row['start_error_m']=float(np.linalg.norm(pp[0]-x['state']['xy']));row['max_step_m']=float(np.linalg.norm(np.diff(pp,axis=0),axis=1).max()) if len(pp)>1 else 0;assert row['start_error_m']<.1;assert np.isfinite(pp).all()
   elif e['status']=='live_control':row['follow_route_available']=e.get('follow_route',{}).get('available')
  except Exception as ex:row.update(status='error',reason=repr(ex))
 rows.append(row);(out/'full-replay.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(json.dumps({'done':len(rows),'total':len(records),'input':x['instruction'],'status':row['status'],'reason':row.get('reason','')},ensure_ascii=False),flush=True)
