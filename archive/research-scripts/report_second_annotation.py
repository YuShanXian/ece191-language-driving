"""Audit and illustrate three methods on the same real left-merge annotation."""
import json,pickle
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from language_selector import action_matches
from evaluate_candidate_checks import load_graph
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.paths import ROOT,sha256,write_json


def main():
    base=ROOT/'runs/project-v2/second-annotation-v1';dest=ROOT/'runs/project-v2/reports';sources={}
    names={'baseline':'Fixed checks','connector-route-second-v1':'Connector geometry','map-tail-second-v1':'Geometry + bounded tail'}
    reports={}
    for name in names:
        source=base/('sequence-report.json' if name=='baseline' else f'sequence-report-{name}.json')
        reports[name]=json.loads(source.read_text());sources[str(source.relative_to(ROOT))]=sha256(source)
    timestamps=[r['timestamp_us'] for r in reports['baseline']['checkpoints']]
    if any([r['timestamp_us'] for r in report['checkpoints']]!=timestamps for report in reports.values()):raise ValueError('Methods use different checkpoints')
    selected=[];summary=[]
    for i,entry in enumerate(reports['baseline']['checkpoints']):
        row={'video_frame':entry['video_frame'],'gps_elapsed_seconds':entry['gps_elapsed_seconds'],'methods':{}}
        arrays={};hashes={}
        for name,report in reports.items():
            r=report['checkpoints'][i];folder=ROOT/'runs'/r['run'];screen_path=folder/'anchored_feasibility.json'
            if sha256(screen_path)!=r['screen_sha256']:raise ValueError('Candidate report changed')
            screen=json.loads(screen_path.read_text());choice=r['selection']['candidate']
            arrays[name]=np.load(folder/'refined_v2_candidates.npz')['world_xy'];hashes[name]=sha256(folder/'internal_0000.npz')
            for source in [screen_path,folder/'refined_v2_candidates.npz',folder/'internal_0000.npz']:sources[str(source.relative_to(ROOT))]=sha256(source)
            if choice is not None:
                c=screen['candidates'][choice-1]
                if not c['passes_current_checks'] or not action_matches(c,'lane_change_left',r['speed_mps']):raise ValueError('Chosen candidate does not pass and match the real instruction')
            row['methods'][name]={'status':r['selection']['status'],'candidate':choice,'passing_candidates':r['passing_candidates']}
            if name=='map-tail-second-v1' and choice is not None:
                c=screen['candidates'][choice-1];raw=np.load(folder/'internal_0000.npz')['world_xy']
                deviation=float(np.linalg.norm(arrays[name][choice-1]-raw[choice-1],axis=1).max())
                if deviation>1.:raise ValueError('Raw deviation bound exceeded')
                selected.append({**r,'extra_tail_shift_m':c['refinement'].get('signed_shift_m',0.),'max_deviation_from_raw_m':deviation,'lane_change':c['route']['lane_changes'][0]})
        if len(set(hashes.values()))!=1:raise ValueError('Methods used different raw MTR arrays')
        if not np.array_equal(arrays['baseline'],arrays['connector-route-second-v1']):raise ValueError('Geometry-only method changed paths')
        if not np.array_equal(arrays['connector-route-second-v1'][:,:30],arrays['map-tail-second-v1'][:,:30]):raise ValueError('First three seconds changed')
        summary.append(row)
    first=reports['baseline']['checkpoints'][0];gps_zero=first['timestamp_us']/1e6-first['gps_elapsed_seconds']
    completed=[e['timestamp']-gps_zero for e in reports['baseline']['final_stage']['history'] if e['event']=='observed_complete']
    audit={'annotation_id':'doplan_000567','instruction':reports['baseline']['instruction'],'checkpoints':summary,
        'selected_detail':[{k:r[k] for k in ['video_frame','gps_elapsed_seconds','extra_tail_shift_m','max_deviation_from_raw_m','lane_change']}|{'candidate':r['selection']['candidate']} for r in selected],
        'observed_completion_gps_seconds':completed,'raw_arrays_identical':True,'geometry_paths_unchanged':True,'first_three_seconds_preserved':True,
        'legacy_metadata_note':'Older comparison.json selected_candidate and map_tail_experiment.selected_candidate fields diagnosed RIGHT merge only. They are not final left-instruction decisions. This report uses and verifies checkpoint selection.candidate against left-action matching; historical files are preserved.',
        'source_sha256':sources,'generator_sha256':sha256(__file__),
        'scope':'Post-hoc development sequence with conditional camera/GPS mapping. Same fixed proposal rules as original example. No execution, no semantic accuracy or validated legal lane-crossing claim.'}
    write_json(base/'three-method-audit.json',audit)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':'#243b50','axes.spines.top':False,'axes.spines.right':False})
    fig=plt.figure(figsize=(14,9));grid=fig.add_gridspec(2,3,height_ratios=[1,1.15],hspace=.42,wspace=.3)
    ax=fig.add_subplot(grid[0,:]);teal='#147e83';grey='#8c9da8'
    for y,(name,report) in zip([2,1,0],reports.items()):
        ax.hlines(y,first['gps_elapsed_seconds'],157,color='#dce3e8')
        for r in report['checkpoints']:
            choice=r['selection']['candidate'];done=r['selection']['status']=='completed'
            ax.scatter(r['gps_elapsed_seconds'],y,marker='s' if done else ('o' if choice else 'x'),color=teal if done or choice else grey,s=65,zorder=3)
            if choice:ax.annotate(f'#{choice}',(r['gps_elapsed_seconds'],y),xytext=(0,-22),textcoords='offset points',ha='center',color=teal,fontsize=9)
    ax.set_yticks([2,1,0],list(names.values()));ax.set_ylim(-.7,3.25);ax.set_xlim(65,162);ax.set_xticks([70,100,120,140,146,150,154,158]);ax.tick_params(axis='x',labelsize=9)
    ax.set_xlabel('Elapsed time from first GPS row (s)');ax.set_title('Same measured checkpoints and original MTR outputs; only the proposal method changes',loc='left',fontsize=11,fontweight='bold')
    for time in completed:
        ax.axvline(time,color=teal,ls=':',lw=1.2)
        ax.annotate(f'Recorded left merge observed complete: {time:.2f} s',(time,2.5),xytext=(95,2.85),arrowprops={'arrowstyle':'->','color':teal},color=teal,fontsize=10)
    for axis,r in zip([fig.add_subplot(grid[1,i]) for i in range(3)],selected):
        folder=ROOT/'runs'/r['run'];sample=ROOT/'samples'/r['sample'];conv=json.loads((sample/'conversion.json').read_text())
        data=np.load(folder/'internal_0000.npz');center=data['center'];theta=float(center[6]);rotation=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
        local=lambda p:(np.asarray(p)[...,:2]-center[:2])@rotation
        graph,_=add_parallel_connector_edges(load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']))
        for node,color in [(r['lane_change']['from'],'#eceff2'),(r['lane_change']['to'],'#d4e9df')]:
            corridor=graph.forward_corridor(node)
            polygons=[corridor] if corridor.geom_type=='Polygon' else list(corridor.geoms)
            for poly in polygons:
                xy=local(poly.exterior.coords);axis.fill(xy[:,0],xy[:,1],color=color,alpha=.7,zorder=0)
        with (sample/conv['scenario']).open('rb') as stream:scenario=pickle.load(stream)
        for feature in scenario['map_features'].values():
            if 'polyline' in feature:
                xy=local(feature['polyline']);axis.plot(xy[:,0],xy[:,1],color='#c9d3db',lw=.6,alpha=.7)
        pool=np.load(folder/'refined_v2_candidates.npz')['world_xy']
        for points in pool:
            xy=local(points);axis.plot(xy[:,0],xy[:,1],color='#a6c1d7',alpha=.35,lw=.6)
        choice=r['selection']['candidate'];xy=local(np.vstack([center[:2],pool[choice-1]]));axis.plot(xy[:,0],xy[:,1],color=teal,lw=2.5)
        axis.scatter(0,0,s=20,color='#243b50');axis.set_xlim(-5,max(25,float(xy[:,0].max())+5));axis.set_ylim(min(-8,float(xy[:,1].min())-4),max(12,float(xy[:,1].max())+4))
        axis.set_aspect('equal',adjustable='box');axis.set_xlabel('Forward (m)');axis.set_ylabel('Left (m)');axis.grid(alpha=.15)
        axis.set_title(f'GPS {r["gps_elapsed_seconds"]:.0f} s · candidate {choice}\nExtra tail shift: {abs(r["extra_tail_shift_m"]):.2f} m',fontsize=10,fontweight='bold')
    fig.suptitle('A second real annotation: "Merge to the left lane."',fontsize=18,fontweight='bold',x=.04,ha='left',y=.98)
    fig.text(.04,.935,'doplan_000567  |  6 checkpoints inside video frames [347, 788)  |  Frozen pretrained MTR, no retraining',fontsize=11)
    fig.legend(handles=[Line2D([],[],marker='x',color=grey,ls='',label='No matching proposal'),Line2D([],[],marker='o',color=teal,ls='',label='Proposed path'),Line2D([],[],marker='s',color=teal,ls='',label='Observed task completion')],loc='lower center',bbox_to_anchor=(.5,.095),frameon=False,ncol=3)
    fig.text(.04,.075,'Maps: equal scales; green line = proposal, green shade = target corridor, grey shade = source corridor. Candidate pool in pale blue.',fontsize=9)
    fig.text(.04,.052,'A left merge is relative to the adjacent road corridor; a curved road need not point upward in this vehicle-fixed view.',fontsize=9)
    fig.text(.04,.027,'Conditional alignment; checkpoints chosen after reviewing the clip; connector legality unverified. No proposed trajectory was executed.',fontsize=9,color='#697887')
    fig.subplots_adjust(left=.19,right=.97,top=.86,bottom=.19)
    fig.savefig(dest/'second-annotation-experiment.png',dpi=180);fig.savefig(dest/'second-annotation-experiment.pdf');plt.close(fig)
    print(json.dumps({'selected':audit['selected_detail'],'observed_completion':completed},indent=2))


if __name__=='__main__':main()
