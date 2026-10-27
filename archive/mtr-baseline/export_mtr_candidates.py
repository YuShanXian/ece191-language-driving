"""Run existing smoke test unchanged; capture final decoder queries before NMS."""
import json,runpy,sys
from pathlib import Path
import numpy as np
import torch
root=Path(__file__).resolve().parent.parent
unitraj=root/'vendor/valeo4cast/UniTraj/unitraj'
for path in [unitraj.parent,unitraj,unitraj/'models/mtr/ops']:
    sys.path.insert(0,str(path))
from unitraj.models.mtr.MTR import MTRDecoder
out=Path(sys.argv[sys.argv.index('--output')+1]).resolve()
original=MTRDecoder.generate_final_prediction
captures=[]
def capture(self,pred_list,batch_dict):
    scores,trajs=original(self,pred_list,batch_dict)
    logits,raw=pred_list[-1]
    inp=batch_dict['input_dict']
    def cpu(t):return t.detach().cpu().numpy().copy()
    captures.append((cpu(raw),cpu(torch.softmax(logits,dim=-1)),cpu(logits),
        cpu(inp['center_objects_world']),cpu(inp['map_center']),cpu(trajs)))
    return scores,trajs
MTRDecoder.generate_final_prediction=capture
try:
    runpy.run_path(str(root/'scripts/smoke_mtr.py'),run_name='__main__')
finally:
    MTRDecoder.generate_final_prediction=original
assert len(captures)==1
raw,scores,logits,centers,map_centers,final=captures[0]
assert np.isfinite(raw).all() and np.isfinite(scores).all()
assert np.allclose(scores.sum(-1),1,atol=1e-6)
manifest=[]
for i in range(len(raw)):
    local=raw[i,:,:,:2];angle=centers[i,6]
    rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    world=local@rotation.T+centers[i,:2]+map_centers[i,:2]
    selected=[]
    for p in final[i,:,:,:2]:
        errors=np.max(abs(local-p),axis=(1,2));idx=int(errors.argmin())
        assert errors[idx]<1e-6
        selected.append(idx)
    previous=np.load(out/f'prediction_{i:04d}.npz')
    assert np.allclose(world[selected],previous['trajectories'],atol=1e-4)
    np.savez_compressed(out/f'internal_{i:04d}.npz',local_xy=local,world_xy=world,
        decoder_features=raw[i],scores=scores[i],logits=logits[i],selected_indices=selected,
        center=centers[i],map_center=map_centers[i])
    manifest.append({'target_index':i,'queries':len(local),'selected_indices_zero_based':selected,
                     'final_five_reconstruction':'passed','shape':list(local.shape)})
(out/'internal_manifest.json').write_text(json.dumps(manifest,indent=2))
print('INTERNAL EXPORT:',json.dumps(manifest))
