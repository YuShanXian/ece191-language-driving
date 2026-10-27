"""Show actual left turns and a high-score road-matched candidate, including rejection."""
import json,pickle
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.affinity import affine_transform
from evaluate_candidate_checks import load_graph
ROOT=Path(__file__).resolve().parent.parent
fig,axes=plt.subplots(1,2,figsize=(12,7))
summary=[]
for ax,gps in zip(axes,[130,150]):
    out=ROOT/f'runs/internal-gps{gps}';sample=ROOT/f'samples/nuplan-gps{gps}'
    conv=json.loads((sample/'conversion.json').read_text())
    with (sample/conv['scenario']).open('rb') as f:ego=pickle.load(f)['tracks']['ego']['state']
    raw=np.load(out/'internal_0000.npz');refined=np.load(out/'refined_candidates.npz')['world_xy'];center=raw['center']
    rows=json.loads((out/'refined_feasibility.json').read_text())['candidates']
    candidates=[r for r in rows if r['route'].get('turns')]
    chosen=max(candidates,key=lambda r:r['score']);idx=chosen['candidate']-1
    h=center[6];c,s=np.cos(h),np.sin(h);matrix=np.array([[s,c],[-c,s]])
    def xy(p):return (p-center[:2])@matrix
    affine=[s,-c,c,s,*(-center[:2]@matrix)]
    graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'])
    for node in graph.nodes.values():
        geom=affine_transform(node.polygon,affine)
        for p in (list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]):
            x,y=p.exterior.xy;ax.fill(x,y,color='#eeeeee',ec='#bfbfbf',lw=.5)
    displayed=[]
    for path,label,color,style in [(ego['position'][20:,:2],'Recorded future (evaluation only)','#1967bb','-'),
                (np.vstack([center[:2],raw['world_xy'][idx]]),'Original MTR','#e18c25','--'),
                (np.vstack([center[:2],refined[idx]]),'Refined candidate','#176a49','-')]:
        p=xy(path);displayed.append(p);ax.plot(p[:,0],p[:,1],style,c=color,lw=2,label=label)
    extent=np.concatenate(displayed)
    ax.set_xlim(extent[:,0].min()-8,extent[:,0].max()+8);ax.set_ylim(extent[:,1].min()-8,extent[:,1].max()+8)
    ax.scatter(0,0,c='black',marker='^',s=50)
    ax.set_aspect('equal');ax.grid(alpha=.2);ax.legend(fontsize=8)
    ax.set_title(f"GPS row {gps}: candidate {idx+1}, score {chosen['score']:.3g}\nRejected by: "+', '.join(chosen['rejected_by']),fontsize=10)
    ax.set_xlabel('Right of initial heading (m)');ax.set_ylabel('Forward (m)')
    summary.append({'gps_row':gps,'candidate':chosen['candidate'],'score':chosen['score'],
                    'in_original_five':chosen['in_original_five'],'rejected_by':chosen['rejected_by'],
                    'motion':chosen['motion'],'body':chosen['body'],'collision':chosen['collision']})
fig.suptitle('MTR contains left-turn forecasts, but these do not pass all current checks',fontsize=13)
fig.tight_layout(rect=[0,0,1,.94]);folder=ROOT/'runs/language-baseline'
fig.savefig(folder/'turn-coverage.png',dpi=160)
(folder/'turn-coverage.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
