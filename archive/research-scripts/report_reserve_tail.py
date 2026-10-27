"""Compare fixed10cm screening with generation that explicitly targets that reserve."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mtr_project.paths import ROOT,sha256,write_json


def main():
    base=ROOT/'runs/project-v2/reserve-tail-v1';path=base/'experiment.json';experiment=json.loads(path.read_text());verify_path=base/'verification.json';verification=json.loads(verify_path.read_text())
    if sha256(path)!=verification['experiment_sha256']:raise ValueError('Verification is for another experiment')
    for name,expected in verification['source_sha256'].items():
        if sha256(ROOT/name)!=expected:raise ValueError('Verified output changed: '+name)
    pool_path=ROOT/experiment['specification']['source_pool'];pool=json.loads(pool_path.read_text());rows=[]
    series=[('development','lane_change_left','Development left'),('development','lane_change_right','Development right'),('annotation-sequence-v1','lane_change_right','Original annotation right'),('second-annotation-v1','lane_change_left','Second annotation left')]
    for group,action,label in series:
        subset=[w for w in experiment['windows'] if w['group']==group and action in w['selections']];old=pool['summary']['groups'][group]['actions'][action]
        rows.append({'group':group,'action':action,'label':label,'active_checkpoints':len(subset),'old_original':old['original_proposals'],'old_filtered_10cm':old['by_margin']['0.10']['proposals'],
            'reserve_generated_10cm':sum(w['selections'][action]['candidate'] is not None for w in subset)})
    selected=[]
    for window in experiment['windows']:
        for action,choice in window['selections'].items():
            candidate=choice['candidate']
            if candidate is None:continue
            entry=next(r for r in verification['verified'] if r['run']==window['run'] and r['candidate']==candidate)
            selected.append({'group':window['group'],'gps_seconds':window['gps_seconds'],'key':window['key'],**entry})
    fig,axes=plt.subplots(1,2,figsize=(14,6),gridspec_kw={'width_ratios':[1.15,1]});ax=axes[0];x=np.arange(4)
    for offset,key,label,color in [(-.23,'old_original','Previous geometry checks','#95a5b4'),(0,'old_filtered_10cm','Same paths +10cm checks','#d79548'),(.23,'reserve_generated_10cm','New tails targeting10cm','#147e83')]:
        bars=ax.bar(x+offset,[r[key] for r in rows],width=.23,label=label,color=color)
        for bar in bars:ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+.05,str(int(bar.get_height())),ha='center',fontsize=9)
    ax.set_xticks(x,['Dev left\n/9 active','Dev right\n/9 active','First right\n/7 active','Second left\n/5 active']);ax.set_ylim(0,4);ax.set_ylabel('Checkpoints with a proposal');ax.set_title('Coverage on the same fixed checkpoints');ax.legend(frameon=False,fontsize=9,loc='upper left');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    ax=axes[1];y=np.arange(len(selected));labels=[r['key'].split('--')[-1]+f' #{r["candidate"]}' for r in selected]
    ax.barh(y,[abs(r['shift_m']) for r in selected],height=.36,label='Tail shift from connector-only path',color='#147e83')
    ax.scatter([r['maximum_raw_deviation_m'] for r in selected],y,color='#d79548',marker='D',s=25,label='Maximum distance from raw MTR',zorder=3)
    ax.set_yticks(y,labels,fontsize=9);ax.invert_yaxis();ax.axvline(1,color='#b33f45',ls='--',lw=1);ax.set_xlim(0,1.05);ax.set_xlabel('Distance (m)');ax.set_title('Selected paths: bounded changes');ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    for axis in axes:axis.spines['top'].set_visible(False);axis.spines['right'].set_visible(False)
    ax.legend(frameon=False,fontsize=8,loc='lower right')
    fig.suptitle('Generate a small reserve, rather than only screening for one',fontsize=18,fontweight='bold',x=.04,ha='left',y=.98)
    fig.text(.04,.92,'23 fixed checkpoints ·164 tested shifts ·9 accepted paths ·5 modified paths · first3s and raw model outputs preserved',fontsize=11)
    fig.text(.04,.08,'The second annotation at GPS146s still has no accepted proposal within this bounded, lane-baseline-directed search.',fontsize=10)
    fig.text(.04,.04,'Post-hoc offline geometry experiment.10cm is not a calibrated safety margin; actuator behavior, map legality and execution remain unverified.',fontsize=9,color='#677987')
    fig.subplots_adjust(left=.065,right=.98,top=.82,bottom=.23,wspace=.65)
    dest=ROOT/'runs/project-v2/reports';fig.savefig(dest/'reserve-tail-comparison.png',dpi=180);fig.savefig(dest/'reserve-tail-comparison.pdf');plt.close(fig)
    result={'experiment_sha256':sha256(path),'verification_sha256':sha256(verify_path),'generator_sha256':sha256(__file__),'comparison':rows,'selected':selected,
        'counts':{'windows':len(experiment['windows']),'accepted':len(verification['verified']),'modified':sum(abs(r['shift_m'])>1e-12 for r in verification['verified']),'trials':sum(w['trials'] for w in experiment['windows'])},
        'scope':experiment['specification']['scope']}
    write_json(base/'report-summary.json',result);print(json.dumps(result['counts']|{'comparison':rows,'selected':selected},indent=2))


if __name__=='__main__':main()
