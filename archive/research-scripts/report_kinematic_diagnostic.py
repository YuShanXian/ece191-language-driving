"""Render inverse-bicycle diagnostics without changing model outputs or choices."""
import json,pickle
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.kinematic_diagnostic import inverse_center_path


def main():
    source=ROOT/'runs/project-v2/kinematic-diagnostic-v1/audit.json';audit=json.loads(source.read_text())
    for mapping in ['source_sha256','implementation_sha256','sdk_source_sha256']:
        for name,expected in audit[mapping].items():
            path=Path(name) if Path(name).is_absolute() else ROOT/name
            if sha256(path)!=expected:raise ValueError('Diagnostic source changed: '+name)
    proposals=audit['proposals'];selected=[r for r in proposals if r['group']!='development']
    worst=max((r for r in proposals if r['group']=='development'),key=lambda r:r['derived']['1']['peak_abs_front_tire_angle_deg'] or -1)
    example=selected+[worst];geometry=audit['geometry'];details=[]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,3,figsize=(14,8),sharex=True)
    for axis,row in zip(axes.flat,example):
        folder=ROOT/'runs'/row['run'];raw=np.load(folder/'internal_0000.npz');points=np.vstack([raw['center'][:2],np.load(folder/'refined_v2_candidates.npz')['world_xy'][row['candidate']-1]])
        heading=float(raw['center'][6]);valid_counts=[]
        for stride,color,label in [(1,'#147e83','10 Hz path'),(2,'#d79548','5 Hz path')]:
            result=inverse_center_path(points[::stride],heading,**geometry,dt=.1*stride)
            if result['summary']!=row['derived'][str(stride)]:raise ValueError('Recomputed requirements differ from audit')
            times=(np.arange(len(result['steering_rad']))+.5)*.1*stride
            axis.plot(times,np.degrees(result['steering_rad']),color=color,lw=1.7,label=label)
            valid_counts.append(f'{int(result["steering_valid"].sum())}/{len(result["steering_valid"])}')
        name=row['run'].rsplit('/',1)[-1]
        axis.set_title(f'{name} · #{row["candidate"]}\nEvaluable segments: {valid_counts[0]} / {valid_counts[1]}',fontsize=10)
        axis.axhline(0,color='#c8d0d6',lw=.8);axis.grid(alpha=.15);axis.set_xlabel('Prediction time (s)');axis.set_ylabel('Implied front-tire angle (deg)')
        axis.set_xlim(0,6)
        details.append({'run':row['run'],'candidate':row['candidate'],**{f'peak_angle_{s}hz':row['derived'][str(k)]['peak_abs_front_tire_angle_deg'] for s,k in [(10,1),(5,2)]}})
    fig.suptitle('Does a plausible-looking path require abrupt steering?',fontsize=18,fontweight='bold',x=.055,ha='left',y=.98)
    fig.text(.055,.932,'Five real-annotation proposals plus the largest-angle development diagnostic; frozen choices are unchanged.',fontsize=11)
    handles,labels=axes.flat[0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.5,.075),ncol=2,frameon=False)
    fig.text(.055,.058,'Rear-axle bicycle inversion from body-center paths; nuPlan Pacifica geometry. Gaps = speed below 0.5 m/s or reverse.',fontsize=9)
    fig.text(.055,.032,'Sampled requirement estimates only: interpolation, low-speed behavior and actuator response remain unresolved. No path was executed.',fontsize=9,color='#677987')
    fig.subplots_adjust(left=.07,right=.98,top=.85,bottom=.20,hspace=.55,wspace=.28)
    dest=ROOT/'runs/project-v2/reports';fig.savefig(dest/'kinematic-diagnostic.png',dpi=180);fig.savefig(dest/'kinematic-diagnostic.pdf');plt.close(fig)
    refs=[r['peak_abs_heading_error_deg'] for r in audit['recorded_references'] if r['peak_abs_heading_error_deg'] is not None]
    summary={'source_sha256':sha256(source),'generator_sha256':sha256(__file__),'counts':audit['summary'],
        'displayed':details,'recorded_reference_windows_with_moving_samples':len(refs),
        'maximum_recorded_reference_heading_error_deg':max(refs) if refs else None,
        'development_above_sdk_default_at_10hz':sum((r['derived']['1']['peak_abs_front_tire_angle_deg'] or 0)>audit['sdk_default_steering_clamp_deg'] for r in proposals if r['group']=='development'),
        'scope':'Descriptive development diagnostics. No calibrated actuator limits, pass/fail update or closed-loop execution.'}
    write_json(ROOT/'runs/project-v2/kinematic-diagnostic-v1/report-summary.json',summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
