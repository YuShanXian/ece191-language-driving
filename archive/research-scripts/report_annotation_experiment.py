"""Render the saved original-annotation experiment without rerunning inference."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from evaluate_candidate_checks import load_graph
from trajectory_checks import footprint, headings
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.paths import ROOT, sha256, write_json


def main():
    folder=ROOT/'runs/project-v2/annotation-sequence-v1'
    paths=[folder/'sequence-report.json',folder/'sequence-report-map-tail-v1.json']
    baseline,variant=[json.loads(p.read_text()) for p in paths]
    if [r['timestamp_us'] for r in baseline['checkpoints']] != [r['timestamp_us'] for r in variant['checkpoints']]:
        raise ValueError('Comparisons must use the same measured timestamps')
    for report in [baseline,variant]:
        for row in report['checkpoints']:
            source=ROOT/'runs'/row['run']/'anchored_feasibility.json'
            if sha256(source)!=row['screen_sha256']:raise ValueError('Screen changed after sequence evaluation')
            paths.append(source)
    first=variant['checkpoints'][0]
    gps_zero=first['timestamp_us']/1e6-first['gps_elapsed_seconds']
    completed=[r['timestamp']-gps_zero for r in variant['final_stage']['history'] if r['event']=='observed_complete']
    selected=[r for r in variant['checkpoints'] if r['selection']['candidate'] is not None]
    detail=next(r for r in selected if r['video_frame']==975)
    run=ROOT/'runs'/detail['run'];before_run=ROOT/'runs/project-v2/connector-route-v1'/detail['source_key']
    conv_path=ROOT/'samples'/detail['sample']/'conversion.json'
    conv=json.loads(conv_path.read_text());screen=json.loads((run/'anchored_feasibility.json').read_text())
    idx=detail['selection']['candidate']-1;candidate=screen['candidates'][idx]
    raw=np.load(run/'internal_0000.npz');center=raw['center']
    before=np.vstack([center[:2],np.load(before_run/'refined_v2_candidates.npz')['world_xy'][idx]])
    after=np.vstack([center[:2],np.load(run/'refined_v2_candidates.npz')['world_xy'][idx]])
    raw_points=np.vstack([center[:2],raw['world_xy'][idx]])
    graph,_=add_parallel_connector_edges(load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']))
    target=graph.forward_corridor(candidate['route']['lane_changes'][0]['to'])
    theta=float(center[6]);rotation=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
    def local(points):return (np.asarray(points)-center[:2])@rotation
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'text.color':'#243b50','axes.labelcolor':'#243b50'})
    fig=plt.figure(figsize=(14,9.2));grid=fig.add_gridspec(2,2,height_ratios=[1,1.4],width_ratios=[1.7,1],hspace=.38,wspace=.25)
    ax=fig.add_subplot(grid[0,:]);teal='#147e83';orange='#c57739';grey='#8496a3'
    for y,report in [(1,baseline),(0,variant)]:
        ax.hlines(y,first['gps_elapsed_seconds'],variant['checkpoints'][-1]['gps_elapsed_seconds'],color='#d6dfe5')
        for r in report['checkpoints']:
            t=r['gps_elapsed_seconds'];choice=r['selection']['candidate'];status=r['selection']['status']
            ax.scatter(t,y,marker='s' if status=='completed' else ('o' if choice else 'x'),s=70,color=teal if choice is not None or status=='completed' else grey,zorder=3)
            if choice is not None:ax.annotate(f'#{choice}',(t,y),xytext=(0,-24),textcoords='offset points',ha='center',color=teal,fontweight='bold')
    for t in completed:
        ax.axvline(t,color=teal,ls=':',lw=1.5)
        ax.annotate(f'Recorded driver: merge observed complete at {t:.1f} s',xy=(t,1.25),xytext=(128,1.5),arrowprops={'arrowstyle':'->','color':teal},fontsize=10,color=teal)
    ax.set_yticks([0,1],['Map-guided tail experiment','Fixed candidate checks']);ax.set_ylim(-.7,2.1);ax.set_xlim(80,207)
    ax.set_xticks([85,120,140,160,180,190,200]);ax.set_xlabel('Elapsed time from first GPS row (s)');ax.set_title('A  |  One persistent instruction, evaluated at eight measured checkpoints',loc='left',fontweight='bold')
    ax.legend(handles=[Line2D([],[],marker='x',color=grey,ls='',label='No matching proposal'),Line2D([],[],marker='o',color=teal,ls='',label='Proposal available'),Line2D([],[],marker='s',color=teal,ls='',label='Task already completed by observation')],loc='upper left',frameon=False,ncol=3,fontsize=9)
    colors=[grey,orange,teal];names=['Raw MTR candidate 6','Bounded smoothing before adjustment','Map-guided proposal (+0.15 m tail)']
    axes=[fig.add_subplot(grid[1,0]),fig.add_subplot(grid[1,1])]
    for axis in axes:
        polygons=[target] if target.geom_type=='Polygon' else list(target.geoms)
        for poly in polygons:
            xy=local(poly.exterior.coords);axis.fill(xy[:,0],xy[:,1],color='#e4efea',edgecolor='#a2baae',lw=.6)
            for ring in poly.interiors:
                xy=local(ring.coords);axis.fill(xy[:,0],xy[:,1],color='white')
        for points,color,name in zip([raw_points,before,after],colors,names):
            xy=local(points);axis.plot(xy[:,0],xy[:,1],color=color,lw=1.7,label=name)
        axis.set_aspect('equal',adjustable='box');axis.grid(alpha=.15);axis.set_xlabel('Forward (m)');axis.set_ylabel('Left (m)')
    xy=local(after);axes[0].set_xlim(-3,xy[:,0].max()+5);axes[0].set_ylim(-8,6)
    axes[0].set_title('B  |  Six-second proposals at GPS time 195 s',loc='left',fontweight='bold')
    fig.legend(handles=[Line2D([],[],color=c,lw=2,label=n) for c,n in zip(colors,names)],loc='upper left',bbox_to_anchor=(.18,.23),frameon=False,fontsize=9)
    for points,color in [(before,orange),(after,teal)]:
        angle=headings(points,float(center[6]))[-1]
        body=footprint(points[-1],angle,float(center[3]),float(center[4]));coords=local(body.exterior.coords)
        axes[1].plot(coords[:,0],coords[:,1],color=color,lw=1.8)
    end=xy[-1];axes[1].set_xlim(end[0]-4,end[0]+4);axes[1].set_ylim(end[1]-3,end[1]+3)
    axes[1].set_title('C  |  Final vehicle body: before / after',loc='left',fontweight='bold',fontsize=10)
    fig.suptitle('From a real doPlan instruction to an offline MTR proposal',fontsize=19,fontweight='bold',x=.05,ha='left',y=.98)
    fig.text(.05,.935,'Instruction: "Merge to the right lane."   |   Annotation doplan_006160   |   Pretrained weights; no retraining',fontsize=11)
    fig.text(.05,.075,'Green region: assumed target corridor. Both map views use equal distance scales. First 3 seconds of the smoothed path stay unchanged.',fontsize=9)
    fig.text(.05,.048,'Post-hoc development example. Connector legality and closed-loop behavior are unverified. Proposals were never executed; recorded completion is independent.',fontsize=9,color='#6e7780')
    fig.subplots_adjust(left=.18,right=.97,top=.87,bottom=.17)
    dest=ROOT/'runs/project-v2/reports';dest.mkdir(parents=True,exist_ok=True)
    fig.savefig(dest/'annotation-experiment.png',dpi=180);fig.savefig(dest/'annotation-experiment.pdf');plt.close(fig)
    paths.extend([conv_path,run/'internal_0000.npz',run/'refined_v2_candidates.npz',before_run/'refined_v2_candidates.npz'])
    write_json(dest/'annotation-experiment-provenance.json',{'sources':{str(p.relative_to(ROOT)):sha256(p) for p in paths},'generator_sha256':sha256(__file__),'recorded_completion_gps_seconds':completed,'selected_checkpoints':[{'frame':r['video_frame'],'candidate':r['selection']['candidate']} for r in selected],'scope':variant['scope']})
    print(dest/'annotation-experiment.png')


if __name__=='__main__':main()
