"""Presentation figure from saved real experiment outputs; no model inference."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
from matplotlib.lines import Line2D
from shapely.affinity import affine_transform
from evaluate_candidate_checks import load_graph

ROOT=Path(__file__).resolve().parent.parent
out=ROOT/'runs/internal-moving'
raw=np.load(out/'internal_0000.npz');center=raw['center']
refined=np.load(out/'refined_v2_candidates.npz')['world_xy']
report=json.loads((out/'language_baseline_anchored.json').read_text())
checks=json.loads((out/'anchored_feasibility.json').read_text())
conv=json.loads((ROOT/'samples/nuplan-moving/conversion.json').read_text())
instructions=['Keep the lane.','Merge to the left lane.']
choices=[next(r for r in report['results'] if r['instruction']==s) for s in instructions]
assert all(c['selected_candidate'] is not None for c in choices)
graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'])
h=center[6];c,s=np.cos(h),np.sin(h);matrix=np.array([[c,-s],[s,c]])
def xy(p):return (p-center[:2])@matrix
offset=-center[:2]@matrix
affine=[c,s,-s,c,*offset]

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.labelcolor':'#405168','xtick.color':'#62748a','ytick.color':'#62748a','svg.fonttype':'none'})
fig=plt.figure(figsize=(16,9),facecolor='white')
ink='#172b46';muted='#596d84';blue='#2266c7';green='#00876c'
fig.text(.055,.944,'Language-guided selection of MTR trajectories',fontsize=24,weight='bold',color=ink)
fig.text(.055,.906,'Initial offline prototype  |  Same driving scene, different instructions  |  Pretrained MTR; no retraining',fontsize=12,color=muted)

def box(x,y,w,h,title,body,accent=ink):
    fig.add_artist(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.008,rounding_size=0.008',
                                transform=fig.transFigure,facecolor='#f5f8fc',edgecolor='#dce5ef',lw=1))
    fig.text(x+.012,y+h-.031,title,fontsize=11,weight='bold',color=accent)
    fig.text(x+.012,y+.017,body,fontsize=9.5,color=muted,linespacing=1.4)
pipeline=[(.055,.18,'1  Observed scene','Past motion + nearby agents\nRoad map'),
          (.278,.18,'2  Frozen MTR','64 trajectory candidates\n6-second prediction horizon'),
          (.501,.18,'3  Refine & screen','Smooth motion; check road,\nvehicle footprint and collisions'),
          (.724,.22,'4  Language selection','Fixed-rule instruction parser\nMatch action, then rank candidates')]
for x,w,title,body in pipeline:box(x,.783,w,.092,title,body)
for left,right in zip(pipeline,pipeline[1:]):
    fig.add_artist(FancyArrowPatch((left[0]+left[1]+.012,.828),(right[0]-.012,.828),
                                 transform=fig.transFigure,arrowstyle='-|>',mutation_scale=13,color='#7e91a9',lw=1.4))

axes=[fig.add_axes([.065,.424,.675,.278]),fig.add_axes([.065,.126,.675,.225])]
colors=[blue,green]
for k,ax in enumerate(axes):
    for node in graph.nodes.values():
        geom=affine_transform(node.polygon,affine)
        for poly in (list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]):
            xs,ys=poly.exterior.xy;ax.plot(xs,ys,c='#d9dfe6',lw=.7,zorder=0)
    for p in raw['world_xy']:
        p=xy(np.vstack([center[:2],p]));ax.plot(p[:,0],p[:,1],c='#9dbfe8',alpha=.42,lw=.75,zorder=1)
    for choice,color in zip(choices,colors):
        p=xy(np.vstack([center[:2],refined[choice['selected_candidate']-1]]))
        ax.plot(p[:,0],p[:,1],c=color,lw=2.6,zorder=4)
        ax.scatter(*p[-1],s=26,c=color,edgecolors='white',linewidths=.7,zorder=5)
    ax.scatter(0,0,c=ink,s=40,edgecolors='white',linewidths=1,zorder=7)
    ax.set_xlim(-5,95);ax.set_ylabel('Left (m)',fontsize=10);ax.grid(alpha=.14,color='#748399')
    ax.set_xlabel('Forward from the current vehicle position (m)',fontsize=10,labelpad=5)
    ax.tick_params(labelsize=9)
    if k==0:
        ax.set_ylim(-11,11);ax.set_aspect('equal',adjustable='box')
        ax.set_title('A  Road view  ·  equal distance scale',loc='left',fontsize=11,color=ink,pad=9,weight='bold')
    else:
        ax.set_ylim(-3.5,5)
        ax.set_title('B  Lateral detail  ·  unequal axis scales; not a steering-angle plot',loc='left',fontsize=11,color=ink,pad=10,weight='bold')

fig.text(.79,.702,'SAME SCENE → DIFFERENT CHOICE',fontsize=10,weight='bold',color=ink)
for i,(choice,color) in enumerate(zip(choices,colors)):
    row=checks['candidates'][choice['selected_candidate']-1]
    y=.535-i*.164
    label='“Keep the lane”' if i==0 else '“Merge to the left lane”'
    box(.784,y,.17,.126,label,
        f"Selected: candidate {choice['selected_candidate']}\nMTR score: {choice['selected_model_score']:.2g}\nMax refinement: {row['refinement']['max_deviation_m']:.2f} m",color)
fig.text(.79,.319,'No suitable candidate → no selection',fontsize=10,weight='bold',color=ink)
fig.text(.79,.275,'Example: “Merge to the right lane”\nreturns no matching candidate.',fontsize=9.5,color=muted,linespacing=1.5)
legend=[Line2D([0],[0],color='#9dbfe8',lw=1.4,label='Raw MTR candidates'),
        Line2D([0],[0],color=blue,lw=2.5,label='Selected: keep lane'),
        Line2D([0],[0],color=green,lw=2.5,label='Selected: merge left')]
fig.legend(handles=legend,loc='lower left',bbox_to_anchor=(.779,.145),frameon=False,fontsize=10,labelspacing=.9)
fig.text(.055,.058,'Scope: one nuPlan scene; manually specified commands; rule-based parsing (no LLM). Selected paths are bounded refinements of MTR outputs.',fontsize=9,color=muted)
fig.text(.055,.035,'The left-merge candidate has a very low model score. This demonstrates candidate coverage, not validated driving reliability. Traffic lights and lane-marking legality are not checked.',fontsize=8.7,color=muted)
dest=ROOT/'runs/language-baseline';dest.mkdir(exist_ok=True)
for extension in ['png','svg']:
    path=dest/f'language-selection-overview.{extension}'
    fig.savefig(path,dpi=240,facecolor='white');print(path,flush=True)
(dest/'language-selection-overview-provenance.json').write_text(json.dumps({
    'run':'internal-moving','sample':'nuplan-moving','choices':choices,
    'source_files':['internal_0000.npz','refined_v2_candidates.npz','anchored_feasibility.json','language_baseline_anchored.json'],
    'note':'Road view is clipped to the displayed axes. Highlighted outputs are refined, not raw MTR.'},indent=2))
