"""Describe the bounded terminal hold, keeping the original 5.8s experiment visible."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mtr_project.paths import ROOT,sha256,write_json
from report_controller_comparison import COLORS,NAMES,label


def main():
    folder=ROOT/'runs/project-v2/controller-terminal-hold-v1';path=folder/'experiment.json';e=json.loads(path.read_text())
    receipt=json.loads((folder/'verification.json').read_text())
    if receipt['experiment_sha256']!=sha256(path):raise ValueError('Unverified terminal experiment')
    parent=json.loads((ROOT/e['specification']['source_experiment']).read_text());rows=e['results'];stats={}
    for controller in COLORS:
        selected=[r for r in rows if r.get('controller')==controller];done=[r for r in selected if r['status']=='completed_terminal_hold']
        stats[controller]=dict(completed=len(done),road_passed=sum(r['simulated_pose_checks']['body_passed'] for r in done),
            cv_passed=sum(r['simulated_pose_checks']['cv_collision_passed'] for r in done),
            road_passes_lost=sum(r['passing_checks_lost']['body_passed'] for r in done),
            cv_passes_lost=sum(r['passing_checks_lost']['cv_collision_passed'] for r in done),
            reverse_free=sum(r['metrics']['reverse_speed_samples']==0 for r in done),
            clamp_free=sum(r['metrics']['model_steering_clamp_samples']==0 for r in done))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,(ax,turn)=plt.subplots(1,2,figsize=(14,7),gridspec_kw={'width_ratios':[1.3,1]})
    for i,p in enumerate(parent['population']):
        for offset,c in zip([-.13,.13],COLORS):
            cases=[r for r in rows if r.get('proposal')==p['key'] and r.get('controller')==c and r['status']=='completed_terminal_hold']
            for r in cases:
                old=r['parent_metrics']['maximum_center_error_m'];new=r['metrics']['maximum_center_error_m'];y=i+offset
                ax.plot([old,new],[y,y],color=COLORS[c],alpha=.55)
                ax.scatter(old,y,facecolors='none',edgecolors=COLORS[c],s=24)
                ax.scatter(new,y,color=COLORS[c],s=24,marker='x' if not r['simulated_pose_checks']['body_passed'] else 'o')
                if p['key'].startswith('turn-'):
                    with np.load(ROOT/r['arrays']) as d:
                        error=np.linalg.norm(d['center_xy']-d['target_center_xy'],axis=1)
                        turn.plot(d['time_s'],error,color=COLORS[c],ls={-3.:'--',0.:'-',3.:':'}[r['initial_tire_angle_deg']],
                            label=f'{NAMES[c]} / {r["initial_tire_angle_deg"]:+.0f}°')
    ax.set_yticks(range(len(parent['population'])),[label(p) for p in parent['population']]);ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
    ax.set_xlabel('Maximum center error (m)');ax.set_title('All 60 cases: open = 5.8 s, filled = 6 s\nCross = body-road check failed',fontsize=11)
    turn.axvspan(5.8,6,color='#f1d8a7',alpha=.5,label='Terminal hold');turn.set_xlim(0,6)
    turn.set_xlabel('Elapsed time (s)');turn.set_ylabel('Center error (m)');turn.grid(alpha=.2);turn.legend(fontsize=8)
    turn.set_title('Partial left turn: all six cases\nLast control update at 5.6 s',fontsize=11)
    fig.suptitle('What changes in the final 0.2 seconds?',fontsize=18,fontweight='bold',x=.03,ha='left')
    fig.text(.03,.91,'Exact 5.8 s prefixes retained; last filtered command held to 6 s. No new controller update or reference extension.',fontsize=10)
    a,b=stats['lqr'],stats['ilqr_iteration_limited']
    fig.text(.03,.055,f'6 s body-road passes: LQR {a["road_passed"]}/30; iLQR {b["road_passed"]}/30. Newly lost: {a["road_passes_lost"]} / {b["road_passes_lost"]}. CV passes: {a["cv_passed"]}/30 / {b["cv_passed"]}/30.',fontsize=10)
    fig.text(.03,.022,'Terminal-policy sensitivity only; not periodic feedback through 6 s, full-turn completion, traffic compliance or vehicle validation.',fontsize=9,color='#5e6871')
    fig.subplots_adjust(left=.19,right=.98,top=.81,bottom=.17,wspace=.36)
    report=ROOT/'runs/project-v2/reports'
    for suffix in ['png','pdf']:fig.savefig(report/('controller-terminal-hold.'+suffix),dpi=180)
    plt.close(fig)
    result=dict(experiment_sha256=sha256(path),verification_sha256=sha256(folder/'verification.json'),controllers=stats,
        trial_count=len(rows),incomplete_parent_count=sum(r['status']=='incomplete_parent' for r in rows),
        turn_rows=[r for r in rows if r.get('proposal','').startswith('turn-')],scope=e['scope'])
    write_json(folder/'report-summary.json',result);print(json.dumps(stats,indent=2))


if __name__=='__main__':main()
