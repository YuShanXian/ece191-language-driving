"""Re-rank action-grounded MTR candidates by simplified tracking reliability."""
import json,numpy as np
from mtr_project.paths import ROOT,write_json,sha256
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.multirate_tracking import track_multirate_path
from evaluate_candidate_checks import load_graph
from map_instruction_candidates import assess
base=ROOT/'runs/project-v3/instruction-priority-v3';out=ROOT/'runs/project-v3/instruction-priority-v4';out.mkdir(exist_ok=True)
parent=json.loads((base/'results.json').read_text());spec=json.loads((ROOT/'config/multirate-tracking-v1.json').read_text());controller=load_lqr_config(ROOT/spec['tracker_config'])
all_audits=[];results=[]
for w in parent['windows']:
 src=w['source_window'];run=ROOT/'runs'/src['run'];conv=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text())
 checks=json.loads((run/'ambiguity_aware_feasibility.json').read_text());rows={r['candidate']:r for r in checks['candidates']}
 center=np.load(run/'internal_0000.npz')['center'];xy=np.load(run/'refined_v2_candidates.npz')['world_xy']
 graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);starts=checks['summary']['past_only_start_nodes']
 unique=sorted(set(k for c in w['choices'] for k in c['mtr_grounded_candidates']));cache={}
 for k in unique:
  p=np.vstack([center[:2],xy[k-1]]);dense=np.empty((121,2));dense[::2]=p;dense[1::2]=(p[:-1]+p[1:])/2;cache[k]=[]
  for angle in [-3.,0.,3.]:
   arrays,m=track_multirate_path(dense,float(center[6]),center[7:9],checks['summary']['initial_acceleration_from_past_only'],angle,controller,spec['motion_model'],control_dt=.1,integration_dt=.025)
   cache[k].append((arrays,m,angle))
 saved=dict(np.load(base/f'scene-{w["scene"]:02d}-selected.npz'));choices=[]
 for j,ch in enumerate(w['choices']):
  alternatives=[]
  for k in ch['mtr_grounded_candidates']:
   cases=[]
   for arrays,m,angle in cache[k]:
    target=assess(arrays['center_xy'][::4],center,graph,starts,ch['action'],{'route':{'matched':False}})
    cases.append({'initial_tire_angle_deg':angle,'target_retained':target is not None,'metrics':m})
   # Traffic/road/collision flags do not veto or score. Reverse/clamp and tracking errors measure controllability.
   count=sum(c['target_retained'] for c in cases)
   issues=sum(c['metrics']['reverse_speed_samples']+c['metrics']['model_steering_clamp_samples'] for c in cases)
   worst=max(c['metrics']['maximum_center_error_m'] for c in cases)
   alternatives.append({'candidate':k,'cases':cases,'target_retained_cases':count,'reverse_or_clamp_samples':issues,'worst_center_error_m':worst,'mtr_score':rows[k]['score']})
  updated=dict(ch)
  if alternatives:
   pick=max(alternatives,key=lambda a:(a['target_retained_cases'],-a['reverse_or_clamp_samples'],-a['worst_center_error_m'],a['mtr_score']))
   k=pick['candidate'];p=np.vstack([center[:2],xy[k-1]])
   updated.update(candidate=k,features=assess(p,center,graph,starts,ch['action'],rows[k]),mtr_score=rows[k]['score'],risk_flags=list(rows[k]['rejected_by']),tracking=pick,previous_v3_candidate=ch.get('candidate'))
   if len(starts)>1:updated['risk_flags'].append('ambiguous_start_lane')
   saved[f'command_{j}']=p
   for arrays,m,angle in cache[k]:
    np.savez_compressed(out/f'scene-{w["scene"]:02d}-command-{j}-steer{angle:+.0f}.npz',**arrays)
   all_audits.append({'scene':w['scene'],'command':j,'alternatives':alternatives})
  elif ch.get('source')=='map_quintic_supplement':
   audit=json.loads((base/'tracking/results.json').read_text())
   updated['tracking']=next(a for a in audit['results'] if a['scene']==w['scene'] and a['command']==j)
  choices.append(updated)
 np.savez_compressed(out/f'scene-{w["scene"]:02d}-selected.npz',**saved)
 results.append({**w,'choices':choices});write_json(out/'results.json',{**parent,'windows':results,'scope':'Instruction-priority offline candidates, re-ranked by target retention and tracking; safety separate.','parent_sha256':sha256(base/'results.json'),'reranker_sha256':sha256(__file__)})
 write_json(out/'tracking-candidate-audit.json',all_audits)
 print('Scene',w['scene'],'tracked',len(unique),'unique MTR curves',flush=True)
print('Complete')
