import json,numpy as np
from mtr_project.paths import ROOT,write_json
from map_instruction_candidates_v2 import supplements,assess
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.multirate_tracking import track_multirate_path
from evaluate_candidate_checks import load_graph,current_obstacles
from trajectory_checks import motion_check,collision_check
base=ROOT/'runs/project-v3/instruction-priority-v4'
data=json.loads((base/'results.json').read_text());spec=json.loads((ROOT/'config/multirate-tracking-v1.json').read_text());controller=load_lqr_config(ROOT/spec['tracker_config'])
out=base/'short-target-repair';out.mkdir(exist_ok=True);results=[]
for w in data['windows']:
 for j,ch in enumerate(w['choices']):
  t=ch.get('tracking',{})
  if 'target_retained_cases' not in t or t['target_retained_cases']==3:continue
  src=w['source_window'];run=ROOT/'runs'/src['run'];conv=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());screen=json.loads((run/'ambiguity_aware_feasibility.json').read_text())
  center=np.load(run/'internal_0000.npz')['center'];graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);starts=screen['summary']['past_only_start_nodes']
  proposals=supplements(center,graph,starts,ch['action'],screen['summary']['initial_acceleration_from_past_only']);tested=[]
  for index,p in enumerate(proposals):
   points=p['points'];dense=np.empty((121,2));dense[::2]=points;dense[1::2]=(points[:-1]+points[1:])/2;cases=[]
   for angle in [-3.,0.,3.]:
    arrays,m=track_multirate_path(dense,float(center[6]),center[7:9],screen['summary']['initial_acceleration_from_past_only'],angle,controller,spec['motion_model'],control_dt=.1,integration_dt=.025)
    retained=assess(arrays['center_xy'][::4],center,graph,starts,ch['action'],{'route':{'matched':False}}) is not None
    cases.append({'angle':angle,'target_retained':retained,'metrics':m})
   tested.append({'index':index,'target_retained_cases':sum(c['target_retained'] for c in cases),'worst_error_m':max(c['metrics']['maximum_center_error_m'] for c in cases),'cases':cases})
  robust=[a for a in tested if a['target_retained_cases']==3]
  result={'scene':w['scene'],'command':j,'proposal_count':len(proposals),'tested':tested,'repair_found':bool(robust)}
  if robust:
   best=min(robust,key=lambda a:a['worst_error_m']);p=proposals[best['index']];np.savez_compressed(out/'selected.npz',points=p['points'])
   obstacles,bad=current_obstacles(conv);body=graph.body_check(p['points'],float(center[6]),float(center[3]),float(center[4]));motion=motion_check(p['points'],center[7:9],initial_acceleration=screen['summary']['initial_acceleration_from_past_only']);collision=collision_check(p['points'],float(center[6]),float(center[3]),float(center[4]),obstacles)
   route=graph.match(p['points'],float(center[6]),start_nodes=starts)
   result.update(selected=best,features=p['features'],target_node=p['target_node'],risk_flags=[k for k,v in [('road_footprint',body['passed']),('motion',motion['passed']),('constant_velocity_collision',collision['passed']),('observed_start_road_route',route['matched'])] if not v])
  results.append(result);print(w['scene'],ch['action'],'proposals',len(proposals),'robust',len(robust),flush=True)
write_json(out/'results.json',results)
