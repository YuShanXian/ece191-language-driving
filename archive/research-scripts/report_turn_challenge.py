"""Draw every registered coverage result plus outcome-independent context examples."""
import json,pickle
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from mtr_project.paths import ROOT,sha256,write_json


def main():
    base=ROOT/'runs/project-v2/turn-challenge-v1';path=base/'evaluation.json';report=json.loads(path.read_text());verified_path=base/'verification.json';verified=json.loads(verified_path.read_text())
    if verified['evaluation_sha256']!=sha256(path) or verified['status']!='passed_declared_turn_challenge_checks':raise ValueError('Unverified report data')
    dest=ROOT/'runs/project-v2/reports';rows=report['windows'];teal='#147e83';orange='#d79548';blue='#b6cee6';navy='#243b50'
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':navy,'axes.spines.top':False,'axes.spines.right':False})
    labels=[]
    for r in rows:
        window=r['window'];reason=window['sampling'];label='/'.join(str(round(s['fraction']*100))+'%' if s['kind']=='fixed_fraction' else 'tag - 2s' for s in reason)
        labels.append(window['key'].split('-t')[0]+' / '+label)
    fig,axes=plt.subplots(1,3,figsize=(15,7),gridspec_kw={'width_ratios':[1.7,1,1]})
    y=np.arange(len(rows));axes[0].barh(y,[r['passing_candidates'] for r in rows],color=teal)
    axes[0].set_yticks(y,labels);axes[0].invert_yaxis();axes[0].set_xlim(0,64);axes[0].set_xlabel('Candidates / 64');axes[0].set_title('All fixed checks passed')
    for ax,instruction in zip(axes[1:],report['specification']['primary_instructions']):
        choices=[next(c for c in r['choices'] if c['instruction']==instruction) for r in rows]
        for offset,pool,color in [(-.16,'all64',teal),(.16,'final5',orange)]:
            ax.barh(y+offset,[len(c[pool]['matching_candidates']) for c in choices],height=.3,color=color,label=pool)
        upper=max(2,1+max(len(c[pool]['matching_candidates']) for c in choices for pool in ['all64','final5']))
        ax.set_yticks(y,['']*len(rows));ax.invert_yaxis();ax.set_xlim(0,upper);ax.set_xticks(range(upper+1));ax.set_xlabel('Passing, action-matching candidates');ax.set_title(instruction);ax.legend(frameon=False)
    fig.suptitle('Four new recordings: unchanged MTR + frozen baseline checks',fontsize=17,fontweight='bold')
    fig.text(.02,.035,'13 unique anchors: 12 fixed-fraction windows + 1 official start-turn window. Missing tags are reported, not replaced.\nCandidate availability is not language accuracy or executed driving success. Original final5 are a subset of the same64.',fontsize=10)
    fig.tight_layout(rect=[0,.1,1,.95]);fig.savefig(dest/'turn-challenge-coverage.png',dpi=180);fig.savefig(dest/'turn-challenge-coverage.pdf');plt.close(fig)
    illustrated=[r for r in rows if any(s['kind']=='official_tag' or s.get('fraction')==.2 for s in r['window']['sampling'])]
    fig,axes=plt.subplots(2,3,figsize=(15,10));flat=axes.flat
    for ax,result in zip(flat,illustrated):
        row=result['window'];folder=ROOT/'runs'/row['run'];sample=ROOT/'samples'/row['sample'];conv=json.loads((sample/'conversion.json').read_text());cached=np.load(folder/'internal_0000.npz');center=cached['center'];angle=float(center[6])
        rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]]);local=lambda p:(np.asarray(p)[...,:2]-center[:2])@rotation
        with (sample/conv['scenario']).open('rb') as stream:scenario=pickle.load(stream)
        for feature in scenario['map_features'].values():
            if 'polyline' in feature:
                xy=local(feature['polyline']);ax.plot(xy[:,0],xy[:,1],color='#cdd5dd',lw=.6,zorder=0)
        trajectories=np.load(folder/'refined_v2_candidates.npz')['world_xy'];screen=json.loads((folder/'anchored_feasibility.json').read_text())
        for trajectory,candidate in zip(trajectories,screen['candidates']):
            xy=local(np.vstack([center[:2],trajectory]));ax.plot(xy[:,0],xy[:,1],color=teal if candidate['passes_current_checks'] else blue,lw=1 if candidate['passes_current_checks'] else .6,alpha=.7)
        future=scenario['tracks']['ego']['state']['position'][20:81,:2];xy=local(future);ax.plot(xy[:,0],xy[:,1],color='#82518b',ls='--',lw=2)
        ax.scatter(0,0,s=24,color=navy);ax.set_xlim(-15,65);ax.set_ylim(-40,40);ax.set_aspect('equal');ax.grid(alpha=.15);ax.set_xlabel('Forward (m)');ax.set_ylabel('Left (m)')
        source='official tag - 2s' if any(s['kind']=='official_tag' for s in row['sampling']) else 'fixed20%'
        choices=' / '.join(('L' if c['action']=='turn_left' else 'R')+': '+(str(c['all64']['candidate']) if c['all64']['candidate'] else 'none') for c in result['choices'])
        ax.set_title(row['key'].split('-t')[0]+' | '+source+f' | {result["speed_mps"]:.1f} m/s\n'+choices,fontsize=11)
    for ax in list(axes.flat)[len(illustrated):]:ax.axis('off')
    fig.suptitle('Turn-context examples selected before inspecting model outcomes',fontsize=17,fontweight='bold')
    fig.legend(handles=[Line2D([],[],color=blue,label='Derived candidate'),Line2D([],[],color=teal,label='Passed frozen checks'),Line2D([],[],color='#82518b',ls='--',label='Recorded future: evaluation context only')],loc='lower center',bbox_to_anchor=(.5,.055),ncol=3,frameon=False)
    fig.text(.03,.025,'Equal-scale local map views; fixed viewing bounds may crop distant trajectories. These are predictions/proposals, not controller rollouts.',fontsize=10)
    fig.tight_layout(rect=[0,.1,1,.94]);fig.savefig(dest/'turn-challenge-examples.png',dpi=170);fig.savefig(dest/'turn-challenge-examples.pdf');plt.close(fig)
    write_json(base/'report-summary.json',{'evaluation_sha256':sha256(path),'verification_sha256':sha256(verified_path),'summary':report['summary'],'illustrated_windows':[r['window']['key'] for r in illustrated],
        'figure_sha256':{name:sha256(dest/name) for name in ['turn-challenge-coverage.png','turn-challenge-coverage.pdf','turn-challenge-examples.png','turn-challenge-examples.pdf']},'generator_sha256':sha256(__file__)})
    print(dest/'turn-challenge-coverage.png')


if __name__=='__main__':main()
