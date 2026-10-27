import argparse,json
from pathlib import Path
from execute_language_plan_v3 import execute as finite

def execute(scene,plan,initial_state=None,mode="safe"):
 from navigation_contract_v10 import normalize
 plan=normalize(plan)
 stages=plan.get('stages',[])
 if plan.get('status')=='parsed' and not plan.get('unresolved_text') and len(stages)==1 and stages[0]['action'] in ('reverse','reverse_continuous'):
  from reverse_motion_v13 import execute_reverse
  return execute_reverse(scene,stages[0],initial_state or {'xy':[0,0],'heading':0,'speed':0})
 control={'continuous_drive','set_speed','speed_up','slow_down','stop','resume','emergency_stop','cancel','hold_stopped'}
 if plan.get('status')=='parsed' and not plan.get('unresolved_text') and stages and all(s['action'] in control and s.get('travel_distance_m') is None for s in stages):
  for s in stages:
   if s.get('constraints') or s.get('target_text') or s.get('completion_text') or s['trigger'] not in ('now','after_previous'):return {'status':'blocked','stages':[],'points':[[0,0]],'speed_mps':[0],'dt':.1,'reason':'This live control needs an unconditional speed or continuous-drive instruction.'}
   v=s.get('target_speed_mps')
   if v is not None and not 0<=v<=15:return {'status':'blocked','stages':[],'points':[[0,0]],'speed_mps':[0],'dt':.1,'reason':'Demo speed range is 0–15 m/s (0–54 km/h).'}
  response={'status':'live_control','commands':[{'action':('stop' if s['action']=='hold_stopped' else s['action']),'speed_mps':s.get('target_speed_mps'),**({'delta_mps':s['speed_delta_mps']} if 'speed_delta_mps' in s else {})} for s in stages],'stages':[],'points':[[0,0]],'speed_mps':[0],'dt':.1}
  if initial_state and any(s['action'] in ('continuous_drive','resume') for s in stages):
   from follow_road_v5 import build
   from mtr_project.paths import ROOT
   manifest=json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text());response['follow_route']=build(next(w for w in manifest if w['scene']==scene),initial_state)
  return response
 if len(stages)==1 and stages[0]['action'] in ('pull_over','park') and initial_state:
  from basic_maneuvers_v14 import roadside_stop
  return roadside_stop(scene,stages[0],initial_state,mode)
 if mode=="free":
  from free_navigation_v8 import execute_free
  result=execute_free(scene,plan,initial_state)
 else:result=finite(scene,plan,initial_state,mode="safe")
 result["mode"]=mode
 if result['status']=='completed_offline' and mode=='free' and stages and stages[-1]['action'] in ('go_straight','keep_lane','turn_left','turn_right','u_turn','lane_change_left','lane_change_right','select_lane','continuous_drive','resume') and not stages[-1].get('stop_at_end') and stages[-1].get('travel_distance_m') is None:
  # Remove stationary horizon padding before handing control back to road following.
  pts=result['points'];speeds=result['speed_mps']
  while len(pts)>2 and sum((pts[-1][i]-pts[-2][i])**2 for i in range(2))<1e-8:pts.pop();speeds.pop()
  for row in result.get('stages',[]):row['end_point']=min(row.get('end_point',len(pts)-1),len(pts)-1)
  result['continue_after_maneuver']=True
 if result['status']=='completed_offline' and stages and stages[-1]['action'] not in ('stop','hold_stopped','emergency_stop','cancel','park','pull_over') and not stages[-1].get('stop_at_end') and (result['speed_mps'][-1]>.05 or result.get('continue_after_maneuver')):
  from follow_road_v5 import build
  from mtr_project.paths import ROOT
  import math
  points=result['points'];delta=[points[-1][i]-points[-2][i] for i in range(2)];state={'xy':points[-1],'heading':result['heading_rad'][-1] if result.get('heading_rad') else math.atan2(delta[1],delta[0]),'speed':result['speed_mps'][-1],'lane_key':next((s['target'] for s in reversed(result.get('stages',[])) if s.get('target')),None)}
  state['history']=(initial_state or {}).get('history',[])+points
  state['lane_reversed']=next((s.get('target_reversed',False) for s in reversed(result.get('stages',[])) if s.get('target')),False)
  manifest=json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text());result['follow_route']=build(next(w for w in manifest if w['scene']==scene),state)
 return result
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--scene',type=int,required=True);a.add_argument('--plan',required=True);a.add_argument('--state');a.add_argument('--mode',choices=['safe','free'],default='safe');args=a.parse_args();p=Path(args.plan);r=execute(args.scene,json.loads(p.read_text(encoding='utf-8-sig')),json.loads(Path(args.state).read_text(encoding='utf-8-sig')) if args.state else None,mode=args.mode);(p.parent/'execution.json').write_text(json.dumps(r));print(json.dumps({'status':r['status'],'stages':r.get('stages',[])}))
