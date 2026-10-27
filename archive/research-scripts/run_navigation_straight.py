import json,shutil,numpy as np
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph
from navigation_straight import navigation_branches,branch_evidence
from instruction_priority_selector import describe
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.multirate_tracking import track_multirate_path
base=ROOT/'runs/project-v3/instruction-priority-v5';out=ROOT/'runs/project-v3/instruction-priority-v6';out.mkdir(exist_ok=True)
data=json.loads((base/'results.json').read_text());spec=json.loads((ROOT/'config/multirate-tracking-v1.json').read_text());controller=load_lqr_config(ROOT/spec['tracker_config']);audits=[]
for w in data['windows']:
 s=w['scene'];saved=dict(np.load(base/f'scene-{s:02d}-selected.npz'));ch=w['choices'][0];ch['straight_semantics']='navigation'
 if s in (3,7):
  src=w['source_window'];run=ROOT/'runs'/src['run'];conv=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());checks=json.loads((run/'ambiguity_aware_feasibility.json').read_text());center=np.load(run/'internal_0000.npz')['center'];xy=np.load(run/'refined_v2_candidates.npz')['world_xy'];graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);starts=checks['summary']['past_only_start_nodes'];decision=navigation_branches(graph,starts,float(center[6]));options=[]
  for row,path in zip(checks['candidates'],xy):
   p=np.vstack([center[:2],path]);route=row['route'];target=branch_evidence(p,float(center[6]),graph,decision)
   if not target or not route.get('matched'):continue
   if not decision['selected']['requires_lane_change'] and route.get('lane_changes'):continue
   if decision['selected']['branch'] not in route.get('route',[]):continue
   dense=np.empty((121,2));dense[::2]=p;dense[1::2]=(p[:-1]+p[1:])/2;cases=[];arrays_list=[]
   for angle in [-3.,0.,3.]:
    arrays,m=track_multirate_path(dense,float(center[6]),center[7:9],checks['summary']['initial_acceleration_from_past_only'],angle,controller,spec['motion_model'],control_dt=.1,integration_dt=.025)
    retained=branch_evidence(arrays['center_xy'][::4],float(center[6]),graph,decision) is not None
    cases.append({'initial_tire_angle_deg':angle,'target_retained':retained,'metrics':m});arrays_list.append(arrays)
   options.append({'row':row,'points':p,'target':target,'cases':cases,'arrays':arrays_list})
  audit={'scene':s,'decision':decision,'alternatives':[{'candidate':o['row']['candidate'],'retained':sum(c['target_retained'] for c in o['cases'])} for o in options]};audits.append(audit)
  if options:
   pick=max(options,key=lambda o:(sum(c['target_retained'] for c in o['cases']),-max(c['metrics']['maximum_center_error_m'] for c in o['cases']),o['row']['score']))
   row=pick['row'];f=describe(pick['points'],float(center[6]),row);f['target']=pick['target'];ch.update(status='destination_grounded_offline',source='MTR_refined',candidate=row['candidate'],mtr_score=row['score'],features=f,risk_flags=row['rejected_by'],navigation=decision,tracking={'cases':pick['cases']},effective_action='follow_road' if decision['mode']=='follow_road_fallback' else 'go_straight');saved['command_0']=pick['points']
   for angle,arrays in zip([-3,0,3],pick['arrays']):np.savez_compressed(out/f'scene-{s:02d}-command-0-steer{angle:+d}.npz',**arrays)
  else:ch['navigation']=decision
  print(json.dumps({'scene':s,'decision':decision,'candidate':ch.get('candidate'),'alternatives':audit['alternatives']},ensure_ascii=False),flush=True)
 np.savez_compressed(out/f'scene-{s:02d}-selected.npz',**saved)
data['straight_semantics']='Navigation: prefer forward road; otherwise follow mapped road bend, explicitly reporting fallback. Limited local branch audit, not global routing.'
write_json(out/'results.json',data);write_json(out/'navigation-audit.json',audits)
