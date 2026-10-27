"""Report all timing settings at common sample times, preserving unfavorable results."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mtr_project.paths import ROOT, sha256, write_json


def main():
    folder = ROOT / 'runs/project-v2/multirate-tracking-v1'
    path = folder / 'experiment.json'
    experiment = json.loads(path.read_text())
    verified_path = folder / 'verification.json'
    verified = json.loads(verified_path.read_text())
    if verified['experiment_sha256'] != sha256(path): raise ValueError('Unverified timing experiment')
    rows = experiment['results']
    population = experiment['population']
    schedule = experiment['specification']['schedule']
    modes = experiment['specification']['modes']
    def find(p, mode, cp, dt):
        return next(r for r in rows if r['proposal']==p and r['mode']==mode and r['control_dt']==cp and r['integration_dt']==dt)
    labels = []
    for p in population:
        key = p['key']
        label = ('New turn' if p['action'].startswith('turn') or 'turn-00-' in key else
                 'Dev 800' if 'development-00-f800' in key else
                 'Orig 950' if 'f0950' in key else 'Orig 975' if 'f0975' in key else
                 'Second 750' if 'f0750' in key else 'Second 770')
        labels.append(f'{label} / q{p["candidate"]}')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':'#243b50'})
    fig, axes = plt.subplots(1,2,figsize=(14,8),sharey=True)
    matrices = []
    for mode in modes:
        matrices.append(np.array([[find(p['key'],mode,s['control_dt'],s['integration_dt'])['common_sample_max_error_m'] for s in schedule] for p in population]))
    vmax = max(m.max() for m in matrices)
    for ax, mode, matrix in zip(axes,modes,matrices):
        im = ax.imshow(matrix,cmap='YlOrRd',vmin=0,vmax=vmax,aspect='auto')
        ax.set_xticks(range(len(schedule)),[f'{s["control_dt"]:.3f}\n{s["integration_dt"]:.3f}' for s in schedule])
        ax.set_yticks(range(len(population)),labels)
        ax.set_xlabel('Control period / motion step (s)')
        ax.set_title('SDK filter at each motion step' if mode=='sdk_substep' else 'Filter once per control period',fontsize=12,pad=12)
        for i,p in enumerate(population):
            for j,s in enumerate(schedule):
                row=find(p['key'],mode,s['control_dt'],s['integration_dt'])
                marker='*' if not row['common_pose_checks']['body_passed'] else ''
                ax.text(j,i,f'{matrix[i,j]:.2f}{marker}',ha='center',va='center',fontsize=10,
                        color='white' if matrix[i,j]>.65*vmax else '#243b50')
        ax.tick_params(length=0)
    fig.suptitle('Controller timing and actuator scheduling both affect tracking',fontsize=17,fontweight='bold',x=.04,ha='left')
    fig.text(.04,.915,'All 10 frozen proposals × 10 schedules · zero initial tire angle · same pretrained paths and official LQR settings',fontsize=11)
    fig.subplots_adjust(left=.16,right=.9,top=.84,bottom=.18,wspace=.15)
    color_ax=fig.add_axes([.925,.25,.015,.5]);fig.colorbar(im,cax=color_ax,label='Maximum center error (m)')
    fig.text(.04,.055,'Errors and * body-road violations use the same 0.1 s sampling grid. Denser per-step checks are retained in the data.\nThe right panel changes actuator scheduling; it is not stock SDK propagation or a calibrated vehicle. Selection is unchanged.',fontsize=9)
    reports=ROOT/'runs/project-v2/reports';fig.savefig(reports/'multirate-tracking.png',dpi=180);fig.savefig(reports/'multirate-tracking.pdf');plt.close(fig)
    comparisons=[]
    for mode in modes:
        for cp in [.1,.05]:
            pairs=[]
            for p in population:
                coarse=find(p['key'],mode,cp,cp);fine=find(p['key'],mode,cp,.025)
                pairs.append({'proposal':p['key'],'coarse_error_m':coarse['common_sample_max_error_m'],
                    'fine_error_m':fine['common_sample_max_error_m'],'delta_error_m':fine['common_sample_max_error_m']-coarse['common_sample_max_error_m'],
                    'coarse_body_passed':coarse['common_pose_checks']['body_passed'],'fine_body_passed':fine['common_pose_checks']['body_passed']})
            comparisons.append({'mode':mode,'control_dt':cp,'pairs':pairs,'lower_error_count':sum(p['delta_error_m'] < -1e-8 for p in pairs),
                'higher_error_count':sum(p['delta_error_m'] > 1e-8 for p in pairs)})
    summary={'experiment_sha256':sha256(path),'verification_sha256':sha256(verified_path),'generator_sha256':sha256(__file__),
        'proposal_count':len(population),'rollout_count':len(rows),'equal_rate_matches':sum(r['equal_rate_max_residual'] is not None for r in rows),
        'common_body_passed':sum(r['common_pose_checks']['body_passed'] for r in rows),'dense_body_passed':sum(r['dense_pose_checks']['body_passed'] for r in rows),
        'common_cv_passed':sum(r['common_pose_checks']['cv_collision_passed'] for r in rows),'dense_cv_passed':sum(r['dense_pose_checks']['cv_collision_passed'] for r in rows),
        'comparisons':comparisons,'turn_rows':[r for r in rows if 'turn-00-' in r['proposal']], 'scope':experiment['scope']}
    write_json(folder/'report-summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['comparisons','turn_rows','scope']},indent=2))


if __name__=='__main__':main()
