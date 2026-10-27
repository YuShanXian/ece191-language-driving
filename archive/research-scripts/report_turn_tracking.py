"""Illustrate the verified partial-turn tracking counterexample without hiding failures."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from evaluate_candidate_checks import load_graph
from trajectory_checks import footprint,headings
from mtr_project.paths import ROOT,sha256,write_json


def main():
    base=ROOT/'runs/project-v2/turn-tracking-v1';path=base/'experiment.json';experiment=json.loads(path.read_text());verified_path=base/'verification.json';verified=json.loads(verified_path.read_text())
    if verified['experiment_sha256']!=sha256(path):raise ValueError('Unverified turn rollouts')
    rows=experiment['results'];nominal=next(r for r in rows if r['simulation_dt']==.05 and r['initial_tire_angle_deg']==0)
    source=ROOT/'runs'/nominal['window']['run'];center=np.load(source/'internal_0000.npz')['center'];conv=json.loads((ROOT/'samples'/nominal['window']['sample']/'conversion.json').read_text());graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map'])
    angle=float(center[6]);rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]]);local=lambda p:(np.asarray(p)[...,:2]-center[:2])@rotation
    data=np.load(ROOT/nominal['arrays']);checked=next(r for r in verified['checks'] if r['key']==nominal['key']);index=round(checked['worst_body_overlap']['time_s']/.05)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':'#243b50','axes.spines.top':False,'axes.spines.right':False})
    fig=plt.figure(figsize=(14,8));grid=fig.add_gridspec(2,2,width_ratios=[1.15,1],wspace=.3,hspace=.42);map_ax=fig.add_subplot(grid[:,0]);error_ax=fig.add_subplot(grid[0,1]);area_ax=fig.add_subplot(grid[1,1])
    boundary=graph.surface.boundary;lines=[boundary] if boundary.geom_type=='LineString' else list(boundary.geoms)
    for line in lines:
        xy=local(line.coords);map_ax.plot(xy[:,0],xy[:,1],color='#aab8c4',lw=1)
    target=local(data['target_center_xy']);actual=local(data['center_xy']);map_ax.plot(target[:,0],target[:,1],color='#147e83',lw=2,label='Target center path');map_ax.plot(actual[:,0],actual[:,1],color='#b34b43',lw=2,ls='--',label='Simulated center path')
    # Show the original geometric body convention, not the inverse-reference heading.
    original=np.vstack([center[:2],np.load(source/'refined_v2_candidates.npz')['world_xy'][nominal['candidate']-1]])
    original_headings=headings(original,float(center[6]));original_index=round(checked['worst_body_overlap']['time_s']/.1)
    for position,h,color in [(original[original_index],original_headings[original_index],'#147e83'),(data['center_xy'][index],data['heading'][index],'#b34b43')]:
        xy=local(footprint(position,float(h),float(center[3]),float(center[4])).exterior.coords);map_ax.plot(xy[:,0],xy[:,1],color=color,lw=2)
    map_ax.scatter(0,0,color='#243b50',s=25);map_ax.set_xlim(-4,23);map_ax.set_ylim(-5,14);map_ax.set_aspect('equal');map_ax.grid(alpha=.15);map_ax.set_xlabel('Forward (m)');map_ax.set_ylabel('Left (m)');map_ax.set_title('Zero initial tire angle, 0.05 s updates\nBody outlines at 5.6 s; equal map scale',fontsize=11);map_ax.legend(frameon=False,loc='upper left')
    colors={-3:'#487eaa',0:'#147e83',3:'#b36e34'}
    for row in rows:
        saved=np.load(ROOT/row['arrays']);color=colors[row['initial_tire_angle_deg']];style='-' if row['simulation_dt']==.05 else '--';label=f'{row["initial_tire_angle_deg"]:+.0f} deg / {row["simulation_dt"]:.2f} s'
        error=np.linalg.norm(saved['center_xy']-saved['target_center_xy'],axis=1);error_ax.plot(saved['time_s'],error,color=color,ls=style,label=label)
        areas=[footprint(p,float(h),float(center[3]),float(center[4])).difference(graph.surface).area for p,h in zip(saved['center_xy'],saved['heading'])]
        area_ax.plot(saved['time_s'],areas,color=color,ls=style)
    error_ax.set_title('Time-aligned center error');error_ax.set_ylabel('Error (m)');error_ax.grid(alpha=.15);error_ax.legend(frameon=False,ncol=2,fontsize=8)
    area_ax.set_title('Part of the vehicle body outside the road region');area_ax.set_ylabel('Outside area (m²)');area_ax.set_xlabel('Simulation time (s)');area_ax.grid(alpha=.15)
    fig.suptitle('A turn proposal can pass geometry and fail vehicle tracking',fontsize=17,fontweight='bold',x=.04,ha='left')
    fig.text(.04,.925,'Candidate 9 · all six settings have some body-road violation · current-CV overlap check passes in all six',fontsize=11)
    fig.text(.04,.045,'At the worst-area time (5.6 s), the farthest vehicle vertex is 0.13–0.34 m outside the road region across settings.\nA partial6s turn, not completed-turn or real-vehicle evidence. Update interval changes controller calls as well as motion integration.',fontsize=9)
    fig.subplots_adjust(left=.07,right=.97,top=.84,bottom=.14);dest=ROOT/'runs/project-v2/reports';fig.savefig(dest/'turn-tracking.png',dpi=180);fig.savefig(dest/'turn-tracking.pdf');plt.close(fig)
    proposal={'window':nominal['window'],'candidate':nominal['candidate'],'total_cases':len(rows),'road_passed_cases':sum(r['simulated_pose_checks']['body_passed'] for r in rows),'cv_passed_cases':sum(r['simulated_pose_checks']['cv_collision_passed'] for r in rows),
              'maximum_error_range_m':[min(r['metrics']['maximum_center_error_m'] for r in rows),max(r['metrics']['maximum_center_error_m'] for r in rows)],
              'worst_area_vertex_distance_range_m':[min(r['worst_body_overlap']['maximum_vertex_outside_m'] for r in verified['checks']),max(r['worst_body_overlap']['maximum_vertex_outside_m'] for r in verified['checks'])],
              'nominal_arrays':nominal['arrays'],'nominal_arrays_sha256':nominal['arrays_sha256']}
    write_json(base/'report-summary.json',{'experiment_sha256':sha256(path),'verification_sha256':sha256(verified_path),'proposals':[proposal],'scope':experiment['scope'],
        'update_interval_note':'Each simulation step calls LQR. The0.05/0.1s cases change the feedback-update frequency as well as numerical integration; they do not isolate integrator error.',
        'generator_sha256':sha256(__file__)})
    print(json.dumps(proposal,indent=2))


if __name__=='__main__':main()
