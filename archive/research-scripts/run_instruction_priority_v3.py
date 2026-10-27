import json,numpy as np
from mtr_project.paths import ROOT,write_json,sha256
from evaluate_candidate_checks import load_graph,current_obstacles
from trajectory_checks import motion_check,collision_check
from map_instruction_candidates import assess,supplements
old=json.loads((ROOT/'runs/project-v3/language-choice-v1/report-reviewed/evaluation.json').read_text())
out=ROOT/'runs/project-v3/instruction-priority-v3';out.mkdir(exist_ok=True)
records=[]
for r in old['windows']:
 w=r['source_window'];run=ROOT/'runs'/w['run'];c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text())
 checks=json.loads((run/'ambiguity_aware_feasibility.json').read_text());starts=checks['summary']['past_only_start_nodes']
 g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map'])
 center=np.load(run/'internal_0000.npz')['center'];xy=np.load(run/'refined_v2_candidates.npz')['world_xy'];choices=[];saved={}
 obstacles,bad=current_obstacles(c)
 for j,prev in enumerate(r['choices']):
  action=prev['action'];valid=[]
  for row,path in zip(checks['candidates'],xy):
   p=np.vstack([center[:2],path]);f=assess(p,center,g,starts,action,row)
   if f:valid.append({'points':p,'features':f,'candidate':row['candidate'],'source':'MTR_refined','mtr_score':row['score'],'risk_flags':row['rejected_by']})
  extra=[]
  if not valid:extra=supplements(center,g,starts,action,checks['summary']['initial_acceleration_from_past_only'])
  if valid:chosen=max(valid,key=lambda x:(x['features']['center_on_road_fraction'],x['mtr_score']))
  elif extra:
   chosen=max(extra,key=lambda x:(x['features']['center_on_road_fraction'],-abs(np.linalg.norm(x['points'][-1]-center[:2])-max(np.linalg.norm(center[7:9])*6,20))))
   p=chosen['points'];body=g.body_check(p,float(center[6]),float(center[3]),float(center[4]))
   motion=motion_check(p,center[7:9],initial_acceleration=checks['summary']['initial_acceleration_from_past_only'])
   collision=collision_check(p,float(center[6]),float(center[3]),float(center[4]),obstacles)
   route=g.match(p,float(center[6]),start_nodes=starts)
   chosen['risk_flags']=[k for k,passed in [('road_footprint',body['passed']),('motion',motion['passed']),('constant_velocity_collision',collision['passed']),('observed_start_road_route',route['matched'])] if not passed]
   chosen['checks']={'body':body,'motion':motion,'collision':collision,'route':route}
  else:chosen=None
  result={'action':action,'instruction':prev['instruction'],'old_candidate':prev['choice']['candidate'],'mtr_grounded_candidates':[x['candidate'] for x in valid],'map_supplement_count':len(extra)}
  if chosen:
   saved[f'command_{j}']=chosen['points']
   result.update({k:v for k,v in chosen.items() if k!='points'})
   result['status']='destination_grounded_offline'
   if len(starts)>1:result['risk_flags']=list(result['risk_flags'])+['ambiguous_start_lane']
  else:result['status']='no_grounded_candidate'
  result['unassessed']=['traffic_light','lane_marking_legality','interactive_traffic_response']
  choices.append(result);print(r['number'],action,result['status'],result.get('source'),flush=True)
 np.savez(out/f'scene-{r["number"]:02d}-selected.npz',**saved)
 records.append({'scene':r['number'],'source_window':w,'choices':choices,'source_sha256':sha256(run/'refined_v2_candidates.npz')})
 write_json(out/'results.json',{'windows':records,'selection_uses':['current_state','past_state','map','MTR_candidates'],'selection_does_not_use':['recorded_future','manual_verdicts','video'],'scope':'Development examples, destination grounding not safety or human-confirmed success','code_sha256':sha256(ROOT/'scripts/map_instruction_candidates.py')})
print('Completed all seven')
