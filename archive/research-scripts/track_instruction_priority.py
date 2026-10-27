"""Offline frozen-path tracking, separate from traffic-safety flags."""
import json,numpy as np
from mtr_project.paths import ROOT,write_json,sha256
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.multirate_tracking import track_multirate_path
from evaluate_candidate_checks import load_graph
from map_instruction_candidates import assess
base=ROOT/'runs/project-v3/instruction-priority-v3'
parent=json.loads((base/'results.json').read_text())
spec=json.loads((ROOT/'config/multirate-tracking-v1.json').read_text())
controller=load_lqr_config(ROOT/spec['tracker_config'])
out=base/'tracking';out.mkdir(exist_ok=True);records=[]
for w in parent['windows']:
 src=w['source_window'];run=ROOT/'runs'/src['run'];conv=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text())
 check=json.loads((run/'ambiguity_aware_feasibility.json').read_text());center=np.load(run/'internal_0000.npz')['center']
 graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map'])
 paths=np.load(base/f'scene-{w["scene"]:02d}-selected.npz')
 for j,ch in enumerate(w['choices']):
  if ch['status']!='destination_grounded_offline':continue
  points=paths[f'command_{j}'];dense=np.empty((121,2));dense[::2]=points;dense[1::2]=(points[:-1]+points[1:])/2
  cases=[]
  for angle in [-3.,0.,3.]:
   arrays,metrics=track_multirate_path(dense,float(center[6]),center[7:9],check['summary']['initial_acceleration_from_past_only'],angle,controller,spec['motion_model'],control_dt=.1,integration_dt=.025)
   # Resample at the same 0.1 s interval used by the target validator.
   simulated=arrays['center_xy'][::4]
   target=assess(simulated,center,graph,check['summary']['past_only_start_nodes'],ch['action'],{'route':{'matched':False}})
   name=f'scene-{w["scene"]:02d}-command-{j}-steer{angle:+.0f}.npz';np.savez_compressed(out/name,**arrays)
   cases.append({'initial_tire_angle_deg':angle,'target_retained':target is not None,'target_evidence':target,'metrics':metrics,'arrays':name})
  result={'scene':w['scene'],'command':j,'action':ch['action'],'source':ch['source'],'cases':cases,'target_retained_all_three':all(c['target_retained'] for c in cases)}
  records.append(result);write_json(out/'results.json',{'source_sha256':sha256(base/'results.json'),'mode':'control_period_filter','control_dt':.1,'integration_dt':.025,'cases_per_path':3,'results':records,'scope':'Simplified frozen-path feedback test. Target retention is not safety or real-car validation.'})
  print(w['scene'],ch['action'],sum(c['target_retained'] for c in cases),'/3',max(c['metrics']['maximum_center_error_m'] for c in cases),flush=True)
print('Complete',len(records),'paths',len(records)*3,'rollouts')
