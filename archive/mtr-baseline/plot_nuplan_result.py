"""Plot two real-data adapter smoke tests; errors are descriptive, not a benchmark."""
import json,pickle
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parent.parent
fig,axes=plt.subplots(2,1,figsize=(13,9),constrained_layout=True)
results=[]
for ax,sample,run,title in zip(axes,['nuplan-one','nuplan-moving'],['nuplan-first','nuplan-moving'],['Stopped ego','Moving ego']):
    scene=pickle.load(open(next((root/'samples'/sample).glob('sd_*.pkl')),'rb'))
    out=root/'runs'/run;d=np.load(out/'prediction_0000.npz')
    s=scene['tracks']['ego']['state'];angle=float(s['heading'][20]);origin=s['position'][20,:2]
    rot=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    gt=s['position'][21:81,:2];pred=d['trajectories']
    assert pred.shape==(5,60,2) and np.isfinite(pred).all()
    assert np.allclose(d['center'][:2],origin,atol=.001)
    future=(gt-origin)@rot;local=(pred-origin)@rot
    for feature in scene['map_features'].values():
        points=(feature['polyline'][:,:2]-origin)@rot
        ax.plot(*points.T,color='#cdd3da',lw=.8,zorder=0)
    hist=(s['position'][:21,:2]-origin)@rot
    ax.plot(*hist.T,'k-',lw=2,label='Observed ego history')
    ax.plot(*future.T,color='#111827',ls='--',lw=2,label='Recorded future (comparison only)')
    for i,(p,score) in enumerate(zip(local,d['scores'])):
        ax.plot(*p.T,lw=1.8,label=f'Candidate {i+1}: score {score:.3f}')
    ax.scatter(0,0,c='black',s=30)
    bounds=np.concatenate([hist,future,local.reshape(-1,2)])
    lo=bounds.min(0)-8;hi=bounds.max(0)+8
    ax.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),xlabel='Forward (m)',ylabel='Left (m)',title=title)
    ax.set_aspect('equal');ax.grid(alpha=.15)
    ax.legend(fontsize=8,loc='center left',bbox_to_anchor=(1.01,.5))
    errors=np.linalg.norm(pred-gt[None],axis=-1)
    metrics={'run':run,'top_score_mode':int(d['scores'].argmax()),'scores':d['scores'].tolist(),
             'ADE_m_per_mode':errors.mean(1).tolist(),'FDE_m_per_mode':errors[:,-1].tolist(),
             'recorded_displacement_m':float(np.linalg.norm(gt[-1]-origin)),
             'scope':'Two-case smoke test only; no language input or planning safety evaluation.'}
    (out/'comparison.json').write_text(json.dumps(metrics,indent=2));results.append(metrics)
fig.suptitle('Pretrained MTR on converted nuPlan data\n5 six-second predictions; experimental cross-dataset adapter, no language conditioning')
out=root/'runs/nuplan-moving/nuplan-comparison.png'
fig.savefig(out,dpi=150);print(json.dumps(results,indent=2));print(out)
