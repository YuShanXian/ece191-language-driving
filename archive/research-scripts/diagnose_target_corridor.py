"""Measure why an otherwise passing proposal does not settle in its target lane."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import Point
from evaluate_candidate_checks import load_graph
from trajectory_checks import footprint,headings
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.paths import ROOT,write_json,sha256


def main():
    run=ROOT/'runs/project-v2/connector-route-v1/doplan_006160-f0975'
    report=json.loads((run/'anchored_feasibility.json').read_text())
    conv=json.loads((ROOT/'samples'/report['summary']['sample']/'conversion.json').read_text())
    graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map'])
    graph,_=add_parallel_connector_edges(graph)
    candidates=np.load(run/'refined_v2_candidates.npz')['world_xy'];center=np.load(run/'internal_0000.npz')['center']
    row=report['candidates'][5];points=np.vstack([center[:2],candidates[5]])
    angles=headings(points,float(center[6]));event=row['route']['lane_changes'][0]
    target=graph.forward_corridor(event['to']);records=[]
    for index in range(len(points)-6,len(points)):
        body=footprint(points[index],angles[index],float(center[3]),float(center[4]))
        records.append({'step':index,'future_seconds':index*.1,'body_inside':bool(target.covers(body)),
                        'outside_area_m2':float(body.difference(target).area),
                        'maximum_corner_distance_outside_m':max(Point(p).distance(target) for p in body.exterior.coords)})
    dest=ROOT/'runs/project-v2/replay-diagnostics/doplan_006160';dest.mkdir(parents=True,exist_ok=True)
    result={'candidate':6,'source':str(run.relative_to(ROOT)),'screen_sha256':sha256(run/'anchored_feasibility.json'),
            'vehicle_length_m':float(center[3]),'vehicle_width_m':float(center[4]),'lane_change':event,'last_half_second':records,
            'scope':'Geometric diagnosis only. No threshold, trajectory, or legality assumption changed.'}
    write_json(dest/'candidate-6-target-corridor.json',result)
    theta=float(center[6]);rotation=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
    def local(xy):return (np.asarray(xy)-center[:2])@rotation
    fig,axes=plt.subplots(1,2,figsize=(13,4.5),gridspec_kw={'width_ratios':[1.7,1]})
    for ax in axes:
        polygons=[target] if target.geom_type=='Polygon' else list(target.geoms)
        for poly in polygons:
            coords=local(poly.exterior.coords);ax.fill(coords[:,0],coords[:,1],color='#d6ebe5',edgecolor='#8eb3a8',lw=.6)
            for ring in poly.interiors:
                coords=local(ring.coords);ax.fill(coords[:,0],coords[:,1],color='white',edgecolor='#8eb3a8',lw=.6)
        xy=local(points);ax.plot(xy[:,0],xy[:,1],color='#147e83',lw=2,label='Derived MTR candidate 6')
        for index in range(len(points)-6,len(points)):
            body=footprint(points[index],angles[index],float(center[3]),float(center[4]));coords=local(body.exterior.coords)
            ax.plot(coords[:,0],coords[:,1],color='#ba6c45',lw=.9,alpha=.7)
        ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.15);ax.set_xlabel('Forward (m)');ax.set_ylabel('Left (m)')
    xy=local(points);axes[0].set_xlim(-2,xy[:,0].max()+5);axes[0].set_ylim(-8,5);axes[0].set_title('Target corridor and predicted body footprints')
    end=xy[-1];axes[1].set_xlim(end[0]-10,end[0]+6);axes[1].set_ylim(end[1]-6,end[1]+5);axes[1].set_title('Last 0.5 seconds: equal distance scale')
    fig.suptitle('Right merge is present, but the predicted vehicle body does not settle within the target corridor',fontsize=12)
    fig.text(.05,.035,'Green: assumed target corridor · Orange: final vehicle footprints · Model proposals, not recorded future or executed motion.',fontsize=9,color='#64768a')
    fig.tight_layout(rect=[0,.08,1,.93]);fig.savefig(dest/'candidate-6-target-corridor.png',dpi=180,bbox_inches='tight');plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
