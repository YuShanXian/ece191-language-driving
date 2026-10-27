"""Explicit GPU audit: changing recorded future must not change prediction."""
import json,pickle,subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent.parent
source=ROOT/'samples/nuplan-moving';dest=ROOT/'samples/nuplan-future-perturbed'
dest.mkdir(exist_ok=False)
for file in source.glob('*.pkl'):
    with file.open('rb') as f:obj=pickle.load(f)
    if isinstance(obj,dict) and 'tracks' in obj:
        for track in obj['tracks'].values():
            state=track['state']
            state['position'][21:,:2]+=np.array([1000.,-2000.])
            state['velocity'][21:]*=-3
            state['heading'][21:]+=1.2
    with (dest/file.name).open('wb') as f:pickle.dump(obj,f)
out=ROOT/'runs/future-independence'
command=[sys.executable,str(ROOT/'scripts/export_mtr_candidates.py'),'--checkpoint',str(ROOT/'weights/pretrained_weights/checkpoint_for_val_test.ckpt'),
         '--data',str(dest),'--output',str(out),'--ego-only']
with (ROOT/'runs/future-independence.log').open('w') as log:
    subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
original=np.load(ROOT/'runs/internal-moving/internal_0000.npz');perturbed=np.load(out/'internal_0000.npz')
checks={key:float(np.max(np.abs(original[key]-perturbed[key]))) for key in ['world_xy','scores']}
passed=all(v<=1e-5 for v in checks.values())
report={'passed':passed,'maximum_absolute_differences':checks,'tolerance':1e-5,
        'scope':'One real scene: all objects future positions, velocities and headings altered after the current frame; validity, past and map unchanged. Not a proof for every configuration.',
        'perturbation':'Future positions +(1000,-2000) metres; velocities times -3; headings +1.2 rad.'}
(out/'independence-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
assert passed, 'Predictions changed when only recorded future changed'
