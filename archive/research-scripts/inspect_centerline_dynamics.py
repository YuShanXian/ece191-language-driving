import json,numpy as np
from pathlib import Path
r=Path('historical-project');out=r/'runs/project-v3/centerline-planner-v1';m=json.loads((r/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text())
for s,j in [(3,0),(5,0),(7,1),(1,2)]:
 p=np.load(out/f'scene-{s:02d}-selected.npz')[f'command_{j}'];c=np.load(r/'runs'/m[s-1]['run']/'internal_0000.npz')['center'];v=np.diff(p,axis=0)/.1;a=np.diff(np.vstack([c[7:9],v]),axis=0)/.1;i=np.argmax(np.linalg.norm(a,axis=1));print(s,j,'peak at',i*.1,'speed near',np.linalg.norm(v[max(0,i-2):i+3],axis=1),'last speeds',np.linalg.norm(v[-5:],axis=1))
