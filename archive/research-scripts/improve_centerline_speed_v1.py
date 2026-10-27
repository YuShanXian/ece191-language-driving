from pathlib import Path
import shutil
root=Path('historical-project');out=root/'runs/project-v3/centerline-planner-v1';initial=out/'initial-run';initial.mkdir(exist_ok=True)
for p in [out/'results.json',out/'config.json',*out.glob('scene-??-selected.npz')]:shutil.copy2(p,initial/p.name)
p=root/'scripts/centerline_trajectory_planner.py';s=p.read_text(encoding='utf-8-sig');s=s.replace("'lateral_accel_mps2':2.5","'lateral_accel_mps2':1.8,'envelope_brake_mps2':.8,'stop_margin_m':5.")
s=s.replace("2*config['brake_mps2']*np.maximum(shape['length']-ds-1,0)","2*config['envelope_brake_mps2']*np.maximum(shape['length']-ds-config['stop_margin_m'],0)")
s=s.replace("2*config['brake_mps2']*(ds[i+1]-ds[i])","2*config['envelope_brake_mps2']*(ds[i+1]-ds[i])")
s=s.replace("distance+max(v*.5,1.)","distance+max(v*1.,2.)")
p.write_text(s,encoding='utf-8')
