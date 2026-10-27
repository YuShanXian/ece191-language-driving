import json,numpy as np
from mtr_project.paths import ROOT,write_json,sha256
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.multirate_tracking import track_multirate_path
base=ROOT/'runs/project-v3/instruction-priority-v4';out=ROOT/'runs/project-v3/instruction-priority-v5';out.mkdir(exist_ok=True)
data=json.loads((base/'results.json').read_text());repairs=json.loads((base/'short-target-repair/results.json').read_text())
for w in data['windows']:
 saved=dict(np.load(base/f'scene-{w["scene"]:02d}-selected.npz'))
 for fix in repairs:
  if fix['scene']!=w['scene'] or not fix['repair_found']:continue
  j=fix['command'];ch=w['choices'][j];old=ch.get('candidate')
  ch.update(source='map_quintic_supplement',candidate=None,previous_v4_candidate=old,mtr_score=None,features=fix['features'],target_node=fix['target_node'],risk_flags=fix['risk_flags'],tracking=fix['selected'],repair='Uniform short-distance sampling and generator/validator threshold consistency; action thresholds unchanged.')
  p=np.load(base/'short-target-repair/selected.npz')['points'];saved[f'command_{j}']=p
  run=ROOT/'runs'/w['source_window']['run'];center=np.load(run/'internal_0000.npz')['center'];check=json.loads((run/'ambiguity_aware_feasibility.json').read_text())
  spec=json.loads((ROOT/'config/multirate-tracking-v1.json').read_text());controller=load_lqr_config(ROOT/spec['tracker_config'])
  dense=np.empty((121,2));dense[::2]=p;dense[1::2]=(p[:-1]+p[1:])/2
  for angle in [-3.,0.,3.]:
   a,m=track_multirate_path(dense,float(center[6]),center[7:9],check['summary']['initial_acceleration_from_past_only'],angle,controller,spec['motion_model'],control_dt=.1,integration_dt=.025)
   np.savez_compressed(out/f'scene-{w["scene"]:02d}-command-{j}-steer{angle:+.0f}.npz',**a)
 np.savez_compressed(out/f'scene-{w["scene"]:02d}-selected.npz',**saved)
data['parent_v4_sha256']=sha256(base/'results.json');data['repair_module_sha256']=sha256(ROOT/'scripts/map_instruction_candidates_v2.py')
write_json(out/'results.json',data)
s=(ROOT/'scripts/report_instruction_priority_v4.py').read_text(encoding='utf-8-sig').replace("out=ROOT/'runs/project-v3/instruction-priority-v4'","out=ROOT/'runs/project-v3/instruction-priority-v5'")
s=s.replace("   if not simpath.exists():simpath=ROOT/f'runs/project-v3/instruction-priority-v3/tracking/", "   if not simpath.exists():simpath=ROOT/f'runs/project-v3/instruction-priority-v4/scene-{s:02d}-command-{j}-steer+0.npz'\n   if not simpath.exists():simpath=ROOT/f'runs/project-v3/instruction-priority-v3/tracking/")
(ROOT/'scripts/report_instruction_priority_v5.py').write_text(s,encoding='utf-8')
print('Final road-target routes:',sum(c['status']=='destination_grounded_offline' for w in data['windows'] for c in w['choices']))
