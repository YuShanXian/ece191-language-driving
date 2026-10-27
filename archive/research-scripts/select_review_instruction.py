"""Text-to-result entry point for the seven fixed offline development scenes."""
import argparse,json
from mtr_project.paths import ROOT
from mtr_project.language import parse_instruction

ACTIONS=['go_straight','turn_left','turn_right','lane_change_left','lane_change_right']
ZH={'\u76f4\u884c':'Go straight','\u76f4\u884c\u6307\u4ee4':'Go straight','\u5de6\u8f6c':'Turn left','\u5de6\u8f6c\u6307\u4ee4':'Turn left','\u53f3\u8f6c':'Turn right','\u53f3\u8f6c\u6307\u4ee4':'Turn right','\u5411\u5de6\u6362\u9053':'Change lanes to the left','\u5411\u5de6\u6362\u9053\u6307\u4ee4':'Change lanes to the left','\u5411\u53f3\u6362\u9053':'Change lanes to the right','\u5411\u53f3\u6362\u9053\u6307\u4ee4':'Change lanes to the right'}
def resolve(scene,instruction,policy='centerline_planner',allow_direction_probe=False):
 if type(scene) is not int or not 1<=scene<=7:return {'status':'unsupported_scene','scene':scene}
 text=ZH.get(instruction.strip(),instruction)
 parsed=parse_instruction(text)
 if parsed['status']!='parsed':return {'status':'unsupported_instruction','parse':parsed}
 if len(parsed['stages'])!=1 or parsed['stages'][0]['trigger']['kind']!='now':
  return {'status':'unsupported_trigger_or_sequence_for_cached_demo','parse':parsed}
 action=parsed['stages'][0]['action']
 if action not in ACTIONS:return {'status':'action_not_available_in_five_command_demo','action':action}
 j=ACTIONS.index(action)
 if policy=='centerline_planner':
  base=ROOT/'runs/project-v3/centerline-planner-v1'
  ch=next(r for r in json.loads((base/'results.json').read_text())['rows'] if r['scene']==scene and r['command']==j)
  return {'scene':scene,'input':instruction,'action':action,'policy':policy,'status':'offline_plan_output','result':ch,'trajectory_file':str(base/f'scene-{scene:02d}-selected.npz'),'trajectory_key':f'command_{j}','scope':'Cached deterministic map-centerline plan for fixed development scene. No MTR candidates used. Risk checks are separate; no obstacle avoidance or live vehicle commands.'}
 if policy=='automatic_roads':
  base=ROOT/'runs/project-v3/automatic-road-v9'
  road=next(r for r in json.loads((base/'predictions.json').read_text())['rows'] if r['scene']==scene and r['command']==j)
  ch=next(r for r in json.loads((base/'trajectory-results.json').read_text())['rows'] if r['scene']==scene and r['command']==j)
  result={'scene':scene,'input':instruction,'action':action,'policy':policy,'road_decision':road,'result':ch,'status':ch['status'],'scope':'Cached automatic map/state/text selection for seven development scenes. Human labels used only in separate evaluation. Rule parser, no LLM, no vehicle commands.'}
  if ch['status']=='route_output':result.update(trajectory_file=str(base/f'scene-{scene:02d}-selected.npz'),trajectory_key=f'command_{j}')
  return result
 if policy=='original_checked':
  old=json.loads((ROOT/'runs/project-v3/language-choice-v1/report-reviewed/evaluation.json').read_text())['windows'][scene-1]['choices'][j]
  return {'scene':scene,'input':instruction,'action':action,'policy':policy,'result':old,'scope':'Original cached conservative result, unchanged.'}
 if policy not in ('instruction_priority','human_targets'):return {'status':'unsupported_policy'}
 base=ROOT/('runs/project-v3/human-target-v8' if policy=='human_targets' else 'runs/project-v3/instruction-priority-v7')
 ch=json.loads((base/'results.json').read_text())['windows'][scene-1]['choices'][j]
 context=({'status':'not_recomputed_for_human_target_policy','trajectory_risk_flags':ch.get('risk_flags',[])} if policy=='human_targets' else next(r for r in json.loads((base/'context-risk.json').read_text())['results'] if r['scene']==scene and r['command']==j))
 result={'scene':scene,'input':instruction,'action':action,'policy':policy,'result':ch,'context_risk':context,'straight_semantics':'navigation','scope':'Cached seven-scene offline experiment. No vehicle commands, no live planning, no LLM.'}
 if policy=='human_targets':result['scope']='Cached human-target-conditioned experiment: annotated feasible roads were used as inputs; not independent language accuracy.'
 if ch['status']=='destination_grounded_offline':
  result.update(status='road_target_output',trajectory_file=str(base/f'scene-{scene:02d}-selected.npz'),trajectory_key=f'command_{j}')
 elif ch['status']=='refused_no_reachable_road':
  result['status']='requested_action_refused'
 elif action=='go_straight':
  result['status']='navigation_road_unresolved'
 elif allow_direction_probe:
  probe_base=ROOT/'runs/project-v3/forced-direction-probes-v1'
  probe=next(r for r in json.loads((probe_base/'results.json').read_text())['results'] if r['scene']==scene and r['command']==j)
  result.update(status='direction_only_no_road_target',result=probe,trajectory_file=str(probe_base/f'scene-{scene:02d}-command-{j}.npz'),trajectory_key='points')
 else:result['status']='no_road_target'
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--scene',type=int,required=True);p.add_argument('--instruction',required=True)
 p.add_argument('--policy',choices=['instruction_priority','original_checked','human_targets','automatic_roads','centerline_planner'],default='centerline_planner')
 p.add_argument('--no-direction-probe',action='store_true')
 p.add_argument('--direction-probe',action='store_true',help='Explicit diagnostic geometry only, not an executable road route')
 args=p.parse_args()
 print(json.dumps(resolve(args.scene,args.instruction,args.policy,args.direction_probe and not args.no_direction_probe),ensure_ascii=False,indent=2))
