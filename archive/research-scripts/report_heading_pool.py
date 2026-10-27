"""Rebuild comparison charts from the complete, fixed passing-pool audit."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mtr_project.corridor_reserve import choose_guarded
from mtr_project.paths import ROOT,sha256,write_json


def main():
    path=ROOT/'runs/project-v2/heading-pool-v1/audit.json';audit=json.loads(path.read_text())
    for mapping in ['source_sha256','implementation_sha256']:
        for name,expected in audit[mapping].items():
            if sha256(ROOT/name)!=expected:raise ValueError('Pool audit source changed: '+name)
    comparisons=[]
    for window in audit['windows']:
        folder=ROOT/'runs'/window['run'];screen=json.loads((folder/'anchored_feasibility.json').read_text())
        conv=json.loads((ROOT/'samples'/screen['summary']['sample']/'conversion.json').read_text())
        entries={r['candidate']:r for r in window['audited_candidates']}
        if set(entries)!={r['candidate'] for r in screen['candidates'] if r['passes_current_checks']}:raise ValueError('Incomplete passing-candidate audit')
        for c in window['comparisons']:
            for margin,recorded in c['by_margin'].items():
                if choose_guarded(screen['candidates'],entries,c['action'],conv['current_speed_mps'],float(margin))!=recorded:raise ValueError('Cannot reproduce guarded choice')
            comparisons.append({'run':window['run'],'group':window['group'],'gps_seconds':window.get('gps_seconds'),**c})
    series=[('development','lane_change_left','Development: left'),('development','lane_change_right','Development: right'),
            ('annotation-sequence-v1','lane_change_right','Original annotation: right'),('second-annotation-v1','lane_change_left','Second annotation: left')]
    methods=[('original','Original checks','#95a5b4'),('0.00','Two headings + 0 cm','#3b8c94'),('0.05','Two headings + 5 cm','#5ba8a6'),('0.10','Two headings + 10 cm','#d79548'),('0.20','Two headings + 20 cm','#b26f39')]
    fig,ax=plt.subplots(figsize=(12,6.2));height=.14;y=np.arange(len(series));labels=[]
    for i,(key,label,color) in enumerate(methods):
        counts=[]
        for group,action,_ in series:
            row=audit['summary']['groups'][group]['actions'][action]
            counts.append(row['original_proposals'] if key=='original' else row['by_margin'][key]['proposals'])
        bars=ax.barh(y+(i-2)*height,counts,height=height,label=label,color=color)
        for bar,n in zip(bars,counts):ax.text(n+.06,bar.get_y()+bar.get_height()/2,str(n),va='center',fontsize=9)
    for group,action,label in series:labels.append(label+f' (active windows: {audit["summary"]["groups"][group]["actions"][action]["active_checkpoints"]})')
    ax.set_yticks(y,labels);ax.invert_yaxis();ax.set_xlim(0,9.8);ax.set_xticks(range(10));ax.set_xlabel('Checkpoints with a proposal');ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False);ax.spines['right'].set_visible(False)
    fig.suptitle('How much lane-change coverage survives extra body checks?',fontsize=17,fontweight='bold',x=.03,ha='left',y=.98)
    fig.text(.03,.91,f'{audit["summary"]["windows"]} fixed checkpoints · all {audit["summary"]["passing_candidates_audited"]} previously passing paths audited · no new trajectories or model inference',fontsize=11)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.18),ncol=3,frameon=False,fontsize=9)
    fig.text(.03,.04,'Target reserves are experimental geometry requirements, not calibrated safety margins. Recorded completion is excluded from active windows.',fontsize=9)
    fig.text(.03,.012,'Development/post-hoc annotation diagnostics only; no semantic-accuracy, legal lane-crossing or closed-loop execution claim.',fontsize=9,color='#677987')
    fig.subplots_adjust(left=.32,right=.97,top=.84,bottom=.24)
    dest=ROOT/'runs/project-v2/reports';fig.savefig(dest/'heading-pool-comparison.png',dpi=180);fig.savefig(dest/'heading-pool-comparison.pdf');plt.close(fig)
    result={'source_sha256':sha256(path),'generator_sha256':sha256(__file__),'summary':audit['summary'],'comparisons':comparisons,'scope':audit['specification']['limits']}
    write_json(path.with_name('report-summary.json'),result);print(json.dumps(audit['summary'],indent=2))


if __name__=='__main__':main()
