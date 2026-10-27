import json,numpy as np
from mtr_project.paths import ROOT
base=ROOT/'runs/project-v3/recording-demo-v1';base.mkdir(exist_ok=True)
scenes={}
for s in range(1,8):
 manifest=json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text())[s-1]
 c=np.load(ROOT/'runs'/manifest['run']/'internal_0000.npz')['center'];h=c[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]])
 def local(p):return np.round((np.asarray(p)[...,:2]-c[:2])@rot,3).tolist()
 old=json.loads((ROOT/'runs/project-v3/automatic-road-v9/candidate-picker-data.json').read_text())['scenes'][str(s)]
 a=np.load(ROOT/f'runs/project-v3/centerline-planner-v1/scene-{s:02d}-selected.npz')
 rows=json.loads((ROOT/'runs/project-v3/centerline-planner-v1/results.json').read_text())['rows']
 result={'scene':s,'roads':list(old['roads'].values()),'trajectories':[local(a[f'command_{j}']) for j in range(5)],'guides':[local(a[f'guide_{j}']) for j in range(5)],'dt':.1,'horizon':12}
 scenes[str(s)]=result
(base/'data.json').write_text(json.dumps({'scenes':scenes}))
print('Exported 7 scenes / 35 trajectories')

