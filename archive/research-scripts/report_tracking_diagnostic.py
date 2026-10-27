"""Describe all fixed controller rollouts without changing prior candidate choices."""
import json
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from evaluate_candidate_checks import load_graph
from mtr_project.connector_routes import add_parallel_connector_edges
from trajectory_checks import footprint
from mtr_project.paths import ROOT,sha256,write_json


def main():
    base=ROOT/'runs/project-v2/tracking-diagnostic-v1';path=base/'experiment.json';audit=json.loads(path.read_text())
    verified_path=base/'verification.json';verified=json.loads(verified_path.read_text())
    if verified['experiment_sha256']!=sha256(path) or verified['rollouts_rechecked']!=54:raise ValueError('Unverified tracking result')
    grouped=defaultdict(list)
    for row in audit['results']:
        if sha256(ROOT/row['arrays'])!=row['arrays_sha256']:raise ValueError('Tracking arrays changed')
        grouped[(row['window'],row['candidate'])].append(row)
    summary=[];cases=[(dt,tire) for dt in [.1,.05] for tire in [-3.,0.,3.]];matrix=[]
    for (window,candidate),rows in grouped.items():
        flags=[next(r['final_half_second_target_reserve'] for r in rows if (r['simulation_dt'],r['initial_tire_angle_deg'])==case) for case in cases];matrix.append(flags)
        nominal=next(r for r in rows if r['simulation_dt']==.05 and r['initial_tire_angle_deg']==0)
        data=np.load(ROOT/nominal['arrays']);delta=data['center_xy']-data['target_center_xy'];theta=data['target_heading']
        lateral=-delta[:,0]*np.sin(theta)+delta[:,1]*np.cos(theta);longitudinal=delta[:,0]*np.cos(theta)+delta[:,1]*np.sin(theta)
        summary.append({'window':window,'candidate':candidate,'action':rows[0]['action'],'selected_by_original_score':rows[0]['was_selected_by_original_score'],
                        'target_reserve_passed_cases':sum(flags),'cases':len(rows),'all_tested_cases_keep_target_reserve':all(flags),
                        'maximum_error_range_m':[min(r['metrics']['maximum_center_error_m'] for r in rows),max(r['metrics']['maximum_center_error_m'] for r in rows)],
                        'nominal_dt005_zero_angle':{**nominal['metrics'],'maximum_abs_lateral_error_m':float(np.abs(lateral).max()),'maximum_abs_longitudinal_error_m':float(np.abs(longitudinal).max()),'target_reserve':nominal['final_half_second_target_reserve'],'arrays':nominal['arrays']}})
    counts={'paths':len(summary),'rollouts':len(audit['results']),'target_reserve_passed':sum(sum(r) for r in matrix),'all_cases_target_paths':sum(r['all_tested_cases_keep_target_reserve'] for r in summary),
            'road_failed_rollouts':sum(not r['simulated_pose_checks']['body_passed'] for r in audit['results']),
            'cv_overlap_rollouts':sum(not r['simulated_pose_checks']['cv_collision_passed'] for r in audit['results']),
            'steering_clamp_rollouts':sum(r['metrics']['model_steering_clamp_samples']>0 for r in audit['results'])}
    fig,axes=plt.subplots(1,2,figsize=(14.2,7),gridspec_kw={'width_ratios':[1.15,1]})
    labels=[r['window'].split('--')[-1]+f' / #{r["candidate"]}'+(' *' if r['selected_by_original_score'] else '') for r in summary]
    axes[0].imshow(np.asarray(matrix),cmap=ListedColormap(['#f4d7d4','#b6ddd7']),vmin=0,vmax=1,aspect='auto')
    for y,line in enumerate(matrix):
        for x,value in enumerate(line):axes[0].text(x,y,'yes' if value else 'no',ha='center',va='center',fontsize=11,color='#183047')
    axes[0].set_xticks(range(6),['0.10s\n-3 deg','0.10s\n0 deg','0.10s\n+3 deg','0.05s\n-3 deg','0.05s\n0 deg','0.05s\n+3 deg'],fontsize=9)
    axes[0].set_yticks(range(9),labels,fontsize=9);axes[0].set_title('Final 0.5s: actual model body keeps 10cm target reserve')
    y=np.arange(len(summary));minimum=np.array([r['maximum_error_range_m'][0] for r in summary]);maximum=np.array([r['maximum_error_range_m'][1] for r in summary]);nominal=np.array([r['nominal_dt005_zero_angle']['maximum_center_error_m'] for r in summary])
    axes[1].hlines(y,minimum,maximum,color='#7996ad',lw=4,label='Range across six fixed settings');axes[1].scatter(nominal,y,color='#147e83',s=45,zorder=3,label='0.05s / zero initial tire angle')
    axes[1].set_yticks(y,['#'+str(r['candidate']) for r in summary]);axes[1].set_ylim(8.5,-.5);axes[1].set_xlim(0,max(maximum)*1.1)
    axes[1].set_title('Largest time-aligned center tracking error');axes[1].set_xlabel('Distance (m)');axes[1].grid(axis='x',alpha=.15);axes[1].legend(fontsize=9,loc='lower right',frameon=False)
    fig.suptitle('A geometrically accepted path is not an exactly followed path',x=.03,ha='left',fontsize=18,fontweight='bold')
    fig.text(.03,.91,f'{counts["paths"]} frozen proposals · {counts["rollouts"]} feedback rollouts · {counts["target_reserve_passed"]}/54 retain target reserve · {counts["all_cases_target_paths"]}/9 retain it in all six settings',fontsize=11)
    fig.text(.03,.07,'* Previously selected by model score. All 9 target paths passed the earlier geometry test; prior choices are unchanged.',fontsize=10)
    fig.text(.03,.025,'Official nuPlan LQR + kinematic bicycle. Fixed 6s plan; assumed initial tire angles; no replanning, reactive traffic or real-vehicle certification.',fontsize=9,color='#607286')
    fig.subplots_adjust(left=.22,right=.98,top=.81,bottom=.19,wspace=.25)
    destination=ROOT/'runs/project-v2/reports';fig.savefig(destination/'tracking-diagnostic.png',dpi=180);fig.savefig(destination/'tracking-diagnostic.pdf');plt.close(fig)
    # Illustrate the pre-existing second annotation at f750 (candidate41), not a
    # newly selected success case. Include the actual final vehicle footprints.
    example=next(r for r in summary if r['window'].endswith('doplan_000567-f0750') and r['candidate']==41)
    parent=json.loads((ROOT/audit['specification']['source_experiment']).read_text());window=next(w for w in parent['windows'] if w['key']==example['window'])
    folder=ROOT/'runs'/window['run'];screen=json.loads((folder/'anchored_feasibility.json').read_text());raw=np.load(folder/'internal_0000.npz');center=raw['center']
    conv=json.loads((ROOT/'samples'/screen['summary']['sample']/'conversion.json').read_text());graph,_=add_parallel_connector_edges(load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']))
    target=graph.forward_corridor(screen['candidates'][40]['route']['lane_changes'][0]['to']).buffer(-.1)
    data=np.load(ROOT/example['nominal_dt005_zero_angle']['arrays']);theta=float(center[6]);rotation=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
    def local(x):return (np.asarray(x)-center[:2])@rotation
    ref=local(data['target_center_xy']);sim=local(data['center_xy'])
    fig,axes=plt.subplots(2,2,figsize=(14,9));fig.suptitle('Second left merge / frame750 / candidate41: target path versus feedback tracking',fontsize=16,fontweight='bold')
    polygons=list(target.geoms) if hasattr(target,'geoms') else [target]
    for ax in axes[0]:
        for polygon in polygons:
            if polygon.geom_type=='Polygon':
                coords=local(polygon.exterior.coords);ax.fill(coords[:,0],coords[:,1],color='#dceee9',zorder=0)
                for ring in polygon.interiors:
                    hole=local(ring.coords);ax.fill(hole[:,0],hole[:,1],color='white',zorder=1)
        ax.plot(ref[:,0],ref[:,1],color='#147e83',lw=2,label='Frozen target center');ax.plot(sim[:,0],sim[:,1],color='#b34b43',lw=2,ls='--',label='Simulated center')
        for t,alpha in [(5.5,.5),(6.,1.)]:
            i=round(t/.05)
            for points,angles,color in [(data['target_center_xy'],data['target_heading'],'#147e83'),(data['center_xy'],data['heading'],'#b34b43')]:
                vertices=local(footprint(points[i],angles[i],float(center[3]),float(center[4])).exterior.coords);ax.plot(vertices[:,0],vertices[:,1],color=color,alpha=alpha,lw=1.2)
        ax.set_aspect('equal',adjustable='box');ax.set_xlabel('Forward (m)');ax.set_ylabel('Left (m)');ax.grid(alpha=.15)
    axes[0,0].set_xlim(min(ref[:,0].min(),sim[:,0].min())-3,max(ref[:,0].max(),sim[:,0].max())+4);axes[0,0].set_ylim(min(ref[:,1].min(),sim[:,1].min())-3,max(ref[:,1].max(),sim[:,1].max())+3);axes[0,0].set_title('Equal-distance map view');axes[0,0].legend(fontsize=9,frameon=False)
    axes[0,1].set_xlim(min(ref[-11:,0].min(),sim[-11:,0].min())-4,max(ref[-11:,0].max(),sim[-11:,0].max())+4);axes[0,1].set_ylim(min(ref[-11:,1].min(),sim[-11:,1].min())-2,max(ref[-11:,1].max(),sim[-11:,1].max())+2);axes[0,1].set_title('Final 0.5s footprints; shaded target eroded by10cm')
    delta=data['center_xy']-data['target_center_xy'];h=data['target_heading'];lateral=-delta[:,0]*np.sin(h)+delta[:,1]*np.cos(h);longitudinal=delta[:,0]*np.cos(h)+delta[:,1]*np.sin(h)
    axes[1,0].plot(data['time_s'],lateral,label='Lateral');axes[1,0].plot(data['time_s'],longitudinal,label='Longitudinal');axes[1,0].set_title('Signed tracking error');axes[1,0].set_ylabel('Error (m)');axes[1,0].legend(frameon=False)
    axes[1,1].plot(data['time_s'],np.degrees(data['tire_angle_rad']),color='#b34b43');axes[1,1].set_title('Simulated front tire angle');axes[1,1].set_ylabel('Angle (deg)')
    for ax in axes[1]:ax.set_xlabel('Time (s)');ax.grid(alpha=.15)
    fig.text(.03,.02,'Zero initial tire angle,0.05s steps. The target reserve fails in all six tested settings for this path; no road/CV-overlap failure was detected.',fontsize=10)
    fig.tight_layout(rect=[.01,.06,.99,.95]);fig.savefig(destination/'tracking-example.png',dpi=180);fig.savefig(destination/'tracking-example.pdf');plt.close(fig)
    result={'experiment_sha256':sha256(path),'verification_sha256':sha256(verified_path),'generator_sha256':sha256(__file__),'counts':counts,'proposals':summary,
            'scope':audit['scope'],'selection_changed':False,'artifacts':{name:sha256(destination/name) for name in ['tracking-diagnostic.png','tracking-diagnostic.pdf','tracking-example.png','tracking-example.pdf']}}
    write_json(base/'report-summary.json',result);print(json.dumps({'counts':counts,'proposals':summary},indent=2))


if __name__=='__main__':main()
