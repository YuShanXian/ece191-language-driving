"""Inspect cached conditional choices; no new model inference or future labels."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.affinity import affine_transform
from evaluate_candidate_checks import load_graph
from trajectory_checks import motion_check

ROOT=Path(__file__).resolve().parent.parent
CASES=[('nuplan-one','internal-stopped'),('nuplan-moving','internal-moving'),('nuplan-lane','internal-lane'),('nuplan-gps700','internal-gps700'),('nuplan-gps900','internal-gps900'),('nuplan-gps130','internal-gps130'),('nuplan-gps150','internal-gps150')]

def refresh_motion_fields():
    for sample,run in CASES:
        out=ROOT/'runs'/run
        center=np.load(out/'internal_0000.npz')['center']
        data=np.load(out/'refined_candidates.npz')['world_xy']
        conv=json.loads((ROOT/'samples'/sample/'conversion.json').read_text())
        graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'])
        path=out/'refined_feasibility.json'
        report=json.loads(path.read_text())
        for row,xy in zip(report['candidates'],data):
            motion=motion_check(np.vstack([center[:2],xy]),center[7:9])
            assert motion['passed']==row['motion']['passed'], 'Existing gate changed; full evaluation required'
            row['motion']=motion
            graph.settled_lane_changes(row['route'],np.vstack([center[:2],xy]),float(center[6]),float(center[3]),float(center[4]))
        path.write_text(json.dumps(report,indent=2))

def plot(v2=False,anchored=False):
    if anchored:v2=True
    for sample,run in CASES:
        out=ROOT/'runs'/run
        conv=json.loads((ROOT/'samples'/sample/'conversion.json').read_text())
        graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'])
        raw=np.load(out/'internal_0000.npz');center=raw['center']
        refined=np.load(out/('refined_v2_candidates.npz' if v2 else 'refined_candidates.npz'))['world_xy']
        checks=json.loads((out/('anchored_feasibility.json' if anchored else ('refined_v2_feasibility.json' if v2 else 'refined_feasibility.json'))).read_text())['candidates']
        results=json.loads((out/('language_baseline_anchored.json' if anchored else ('language_baseline_v2.json' if v2 else 'language_baseline.json'))).read_text())['results']
        requested=['Keep the lane.','Merge to the left lane.','Merge to the right lane.'] if run=='internal-moving' else ['Keep the lane.','Slow down.','Remain stopped.']
        if run in ('internal-gps130','internal-gps150'):requested=['Go straight.','Turn left.','Turn right.']
        h=center[6];c,s=np.cos(h),np.sin(h)
        # Plot forward as y, left as negative x: driver perspective from above.
        matrix=np.array([[s,c],[-c,s]])
        def transform(xy):return (xy-center[:2])@matrix
        offset=-center[:2]@matrix
        affine=[s,-c,c,s,*offset]
        fig,axes=plt.subplots(1,3,figsize=(13,8),sharex=True,sharey=True)
        allxy=transform(refined.reshape(-1,2))
        passing=[xy for r,xy in zip(checks,refined) if r['passes_current_checks']]
        valid_xy=transform(np.concatenate(passing)) if passing else allxy
        ymax=max(15,float(valid_xy[:,1].max())+5)
        for ax,instruction in zip(axes,requested):
            for node in graph.nodes.values():
                geom=affine_transform(node.polygon,affine)
                polygons=list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]
                for poly in polygons:
                    x,y=poly.exterior.xy;ax.fill(x,y,color='#eeeeee',ec='#bbbbbb',lw=.4)
            for row,xy in zip(checks,refined):
                if row['passes_current_checks']:
                    p=transform(np.vstack([center[:2],xy]));ax.plot(p[:,0],p[:,1],color='#a5bbd4',alpha=.5,lw=1)
            choice=next(r for r in results if r['instruction']==instruction)
            idx=choice['selected_candidate']
            subtitle='No matching candidate'
            if idx is not None:
                r=checks[idx-1]
                p=transform(np.vstack([center[:2],raw['world_xy'][idx-1]]));ax.plot(p[:,0],p[:,1],'--',color='#f49d37',lw=1.5,label='Original MTR')
                p=transform(np.vstack([center[:2],refined[idx-1]]));ax.plot(p[:,0],p[:,1],color='#176a49',lw=2.5,label='Refined choice')
                subtitle=f"Candidate {idx}; MTR score {r['score']:.2g}\nMax refinement {r['refinement']['max_deviation_m']:.2f} m"
                ax.legend(loc='upper right',fontsize=8)
            ax.scatter(0,0,c='black',marker='^',s=45,zorder=5)
            ax.set_title(instruction+'\n'+subtitle,fontsize=10)
            xmin=min(-12,float(valid_xy[:,0].min())-3);xmax=max(12,float(valid_xy[:,0].max())+3)
            ax.set_xlim(xmin,xmax);ax.set_ylim(-5,ymax);ax.set_aspect('equal');ax.grid(alpha=.2)
            ax.set_xlabel('Right of current heading (m)')
        axes[0].set_ylabel('Forward from current vehicle position (m)')
        version='v2 + observed start lane' if anchored else f'v{2 if v2 else 1}'
        fig.suptitle(run+f': same scene, different instructions ({version})',fontsize=14)
        fig.text(.5,.025,'Offline diagnostic: bounded-refined forecasts; current checks omit traffic lights and lane-marking legality.\nCommands are manually specified, not timestamp-verified doPlan annotations.',ha='center',fontsize=9)
        fig.tight_layout(rect=[0,.07,1,.94])
        dest=out/('language-choices-anchored.png' if anchored else ('language-choices-v2.png' if v2 else 'language-choices.png'));fig.savefig(dest,dpi=160);plt.close(fig);print(dest,flush=True)

if __name__=='__main__':
    import sys
    if '--refresh-motion' in sys.argv:refresh_motion_fields()
    else:plot('--v2' in sys.argv,'--anchored' in sys.argv)
