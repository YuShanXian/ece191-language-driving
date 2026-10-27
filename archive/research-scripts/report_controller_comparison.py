"""Show every controller comparison, including failures and unfavorable pairs."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from evaluate_candidate_checks import load_graph
from trajectory_checks import footprint
from mtr_project.paths import ROOT,sha256,write_json


NAMES={'lqr':'LQR','ilqr_iteration_limited':'iLQR (iteration limited)'}
COLORS={'lqr':'#477da6','ilqr_iteration_limited':'#148278'}


def label(proposal):
    key=proposal['key']
    group=('New turn' if key.startswith('turn-') else 'Dev 800' if 'development-00-f800' in key else
           'Orig 950' if 'f0950' in key else 'Orig 975' if 'f0975' in key else 'Second 750' if 'f0750' in key else 'Second 770')
    return f'{group} / q{proposal["candidate"]}'


def main():
    folder=ROOT/'runs/project-v2/controller-comparison-v1';path=folder/'experiment.json';experiment=json.loads(path.read_text())
    verification_path=folder/'verification.json';verified=json.loads(verification_path.read_text())
    if verified['experiment_sha256']!=sha256(path):raise ValueError('Unverified controller experiment')
    rows=experiment['results'];population=experiment['population'];spec=experiment['specification'];stats={};pairs=[]
    for controller in spec['controllers']:
        selected=[r for r in rows if r['controller']==controller];completed=[r for r in selected if r['status']=='completed']
        latencies=[d['command_latency_seconds']*1000 for r in completed for d in r['diagnostics']]
        stats[controller]={'trials':len(selected),'completed':len(completed),'failed':len(selected)-len(completed),
            'road_passed':sum(r['simulated_pose_checks']['body_passed'] for r in completed),
            'cv_passed':sum(r['simulated_pose_checks']['cv_collision_passed'] for r in completed),
            'reverse_free':sum(r['metrics']['reverse_speed_samples']==0 for r in completed),
            'clamp_free':sum(r['metrics']['model_steering_clamp_samples']==0 for r in completed),
            'command_calls':len(latencies),'latency_median_ms':float(np.median(latencies)) if latencies else None,
            'latency_p95_ms':float(np.percentile(latencies,95)) if latencies else None,
            'latency_max_ms':float(max(latencies)) if latencies else None,
            'solver_final_cost_higher_than_initial_calls':sum(d['costs'][-1]>d['costs'][0]+1e-8 for r in completed for d in r['diagnostics'] if 'costs' in d),
            'solver_iteration_limit_calls':sum(d.get('iterations',0)==20 for r in completed for d in r['diagnostics'])}
    for p in population:
        for angle in spec['initial_tire_angles_deg']:
            paired={c:next(r for r in rows if r['proposal']==p['key'] and r['controller']==c and r['initial_tire_angle_deg']==angle) for c in spec['controllers']}
            comparable=all(r['status']=='completed' for r in paired.values())
            pairs.append({'proposal':p['key'],'initial_tire_angle_deg':angle,'comparable':comparable,
                'lqr_max_error_m':paired['lqr']['metrics']['maximum_center_error_m'] if comparable else None,
                'ilqr_max_error_m':paired['ilqr_iteration_limited']['metrics']['maximum_center_error_m'] if comparable else None,
                'delta_ilqr_minus_lqr_m':paired['ilqr_iteration_limited']['metrics']['maximum_center_error_m']-paired['lqr']['metrics']['maximum_center_error_m'] if comparable else None})
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':'#243b50','axes.spines.top':False,'axes.spines.right':False})
    fig=plt.figure(figsize=(14,8));grid=fig.add_gridspec(2,2,width_ratios=[1.35,1],wspace=.38,hspace=.55)
    errors=fig.add_subplot(grid[:,0]);checks=fig.add_subplot(grid[0,1]);latency=fig.add_subplot(grid[1,1])
    for i,p in enumerate(population):
        for offset,controller in zip([-.14,.14],spec['controllers']):
            cases=[r for r in rows if r['proposal']==p['key'] and r['controller']==controller]
            complete=[r for r in cases if r['status']=='completed'];color=COLORS[controller]
            if complete:
                values=[r['metrics']['maximum_center_error_m'] for r in complete]
                nominal=next((r for r in complete if r['initial_tire_angle_deg']==0.),None)
                point=nominal['metrics']['maximum_center_error_m'] if nominal else float(np.mean(values))
                errors.errorbar(point,i+offset,xerr=[[point-min(values)],[max(values)-point]],fmt='o' if nominal else 'x',
                    color=color,capsize=4,label=NAMES[controller] if i==0 else None)
            if len(complete)!=3:errors.text(0,i+offset,f'{3-len(complete)} failed',va='center',color='#b34b43',fontsize=8)
    errors.set_yticks(range(len(population)),[label(p) for p in population]);errors.invert_yaxis();errors.grid(axis='x',alpha=.2)
    errors.set_xlabel('Maximum time-aligned center error (m)');errors.set_title('Every proposal: dot = zero initial tire angle\nBar = range over −3°, 0°, +3° assumptions',fontsize=11);errors.legend(frameon=False,fontsize=9)
    x=np.arange(4);width=.34;categories=['Completed','Body-road','CV overlap','No reverse']
    for offset,controller in zip([-.17,.17],spec['controllers']):
        s=stats[controller];counts=[s[k] for k in ['completed','road_passed','cv_passed','reverse_free']]
        bars=checks.bar(x+offset,counts,width,color=COLORS[controller])
        checks.bar_label(bars,fontsize=9,padding=3)
    checks.set_xticks(x,categories,fontsize=9);checks.set_ylim(0,35);checks.set_ylabel('Trials out of 30');checks.set_title('Descriptive checks, not driving success',fontsize=11);checks.grid(axis='y',alpha=.15)
    for i,controller in enumerate(spec['controllers']):
        s=stats[controller]
        if s['latency_median_ms'] is not None:
            latency.plot([i,i],[s['latency_median_ms'],s['latency_p95_ms']],color=COLORS[controller],lw=4)
            latency.scatter(i,s['latency_median_ms'],color=COLORS[controller],s=50)
            latency.scatter(i,s['latency_p95_ms'],color=COLORS[controller],marker='_',s=140)
            latency.text(i+.06,s['latency_p95_ms'],f'p95 {s["latency_p95_ms"]:.1f}',fontsize=9)
    latency.set_xticks([0,1],['LQR','iLQR']);latency.set_xlim(-.5,1.7);latency.set_ylabel('Command time (ms)');latency.set_title('Measured median and p95 on this machine\nTimeout disabled for iLQR; no real-time guarantee',fontsize=10);latency.grid(axis='y',alpha=.15)
    fig.suptitle('Two configured controllers, the same frozen paths',fontsize=18,fontweight='bold',x=.035,ha='left')
    fig.text(.035,.92,'10 proposals × 2 controllers × 3 tire-angle assumptions · common 5.8 s horizon · 0.2 s control / 0.05 s motion',fontsize=11)
    fig.subplots_adjust(left=.145,right=.97,top=.82,bottom=.16)
    fig.text(.035,.045,'Both use the declared control-period actuator filter. iLQR retains 20 iterations but removes the 0.05 s wall-clock limit.\nInternal horizons, costs and limits differ: this compares controller configurations, not the optimization algorithm alone. No candidate selection changed.',fontsize=9)
    destination=ROOT/'runs/project-v2/reports';fig.savefig(destination/'controller-comparison.png',dpi=180);fig.savefig(destination/'controller-comparison.pdf');plt.close(fig)
    turn=next(p for p in population if p['key'].startswith('turn-'));turn_rows=[r for r in rows if r['proposal']==turn['key']]
    conv=json.loads((ROOT/turn['conversion']).read_text());center=np.load(ROOT/'runs'/turn['window']['run']/'internal_0000.npz')['center']
    graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map'])
    angle=float(center[6]);rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]]);local=lambda a:(np.asarray(a)[...,:2]-center[:2])@rotation
    fig=plt.figure(figsize=(14,8));grid=fig.add_gridspec(2,2,width_ratios=[1.1,1],wspace=.3,hspace=.4);map_ax=fig.add_subplot(grid[:,0]);error_ax=fig.add_subplot(grid[0,1]);area_ax=fig.add_subplot(grid[1,1])
    lines=[graph.surface.boundary] if graph.surface.boundary.geom_type=='LineString' else list(graph.surface.boundary.geoms)
    for line in lines:
        xy=local(line.coords);map_ax.plot(xy[:,0],xy[:,1],color='#b6c2cc',lw=1)
    target=np.load(ROOT/turn['reference_arrays'])['target_center_xy'][:117];xy=local(target);map_ax.plot(xy[:,0],xy[:,1],color='#243b50',lw=2,ls=':',label='Target center path (0–5.8 s)')
    for row in turn_rows:
        data=np.load(ROOT/row['arrays']);color=COLORS[row['controller']];tire=row['initial_tire_angle_deg'];style={-3.:'--',0.:'-',3.:':'}[tire]
        if tire==0.:
            xy=local(data['center_xy']);map_ax.plot(xy[:,0],xy[:,1],color=color,lw=2,label=NAMES[row['controller']])
            if data['time_s'][-1]>=5.6:
                i=round(5.6/spec['integration_dt_seconds']);body=footprint(data['center_xy'][i],data['heading'][i],float(center[3]),float(center[4]));xy=local(body.exterior.coords);map_ax.plot(xy[:,0],xy[:,1],color=color,lw=2)
        error=np.linalg.norm(data['center_xy']-data['target_center_xy'],axis=1)
        error_ax.plot(data['time_s'],error,color=color,ls=style,label=f'{NAMES[row["controller"]]} / {tire:+.0f}°')
        area=[footprint(p,h,float(center[3]),float(center[4])).difference(graph.surface).area for p,h in zip(data['center_xy'],data['heading'])]
        area_ax.plot(data['time_s'],area,color=color,ls=style)
    map_ax.set_aspect('equal');map_ax.set_xlim(-4,23);map_ax.set_ylim(-5,14);map_ax.set_xlabel('Forward (m)');map_ax.set_ylabel('Left (m)');map_ax.grid(alpha=.15);map_ax.legend(frameon=False,fontsize=9);map_ax.set_title('Zero initial tire angle; body outlines at 5.6 s',fontsize=11)
    error_ax.set_title('Time-aligned center error');error_ax.set_ylabel('Error (m)');error_ax.grid(alpha=.15);error_ax.legend(frameon=False,fontsize=8,ncol=2)
    area_ax.set_title('Part of the body outside the road region');area_ax.set_ylabel('Outside area (m²)');area_ax.set_xlabel('Simulation time (s)');area_ax.grid(alpha=.15)
    fig.suptitle('Partial left turn: keep the tracking failures visible',fontsize=18,fontweight='bold',x=.035,ha='left')
    fig.text(.035,.92,'Candidate 9 · same initial observations, path and actuator settings · both stopped at 5.8 s without extending the reference',fontsize=11)
    fig.subplots_adjust(left=.07,right=.97,top=.83,bottom=.15)
    fig.text(.035,.045,'Line styles are the same three assumed tire angles for both controllers; they are not measured uncertainty bounds.\nThe target is a partial turn. Body-road and constant-velocity actor checks do not establish traffic-rule compliance or real driving capability.',fontsize=9)
    fig.savefig(destination/'controller-turn-comparison.png',dpi=180);fig.savefig(destination/'controller-turn-comparison.pdf');plt.close(fig)
    comparable=[p for p in pairs if p['comparable']]
    summary={'experiment_sha256':sha256(path),'verification_sha256':sha256(verification_path),'generator_sha256':sha256(__file__),
        'per_controller':stats,'pairs':pairs,'paired_completed_trials':len(comparable),
        'ilqr_lower_error_pairs':sum(p['delta_ilqr_minus_lqr_m']<-1e-8 for p in comparable),
        'ilqr_higher_error_pairs':sum(p['delta_ilqr_minus_lqr_m']>1e-8 for p in comparable),
        'turn_rows':[{k:r[k] for k in ['controller','initial_tire_angle_deg','status','metrics','simulated_pose_checks']} for r in turn_rows],
        'scope':spec['scope'],'configuration_limitations':spec['comparison_scope']}
    write_json(folder/'report-summary.json',summary);print(json.dumps({k:v for k,v in summary.items() if k not in ['pairs','turn_rows','scope','configuration_limitations']},indent=2))


if __name__=='__main__':main()
