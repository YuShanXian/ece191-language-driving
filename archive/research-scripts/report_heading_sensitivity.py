"""Show target-corridor failures caused solely by alternative body heading."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import Point
from trajectory_checks import headings,footprint
from evaluate_candidate_checks import load_graph
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.kinematic_diagnostic import inverse_center_path
from mtr_project.pose_geometry import interpolate_centers_and_angles
from mtr_project.paths import ROOT,sha256,write_json


def main():
    source=ROOT/'runs/project-v2/heading-sensitivity-v1/audit.json';audit=json.loads(source.read_text())
    for mapping in ['source_sha256','implementation_sha256']:
        for name,expected in audit[mapping].items():
            if sha256(ROOT/name)!=expected:raise ValueError('Heading audit source changed: '+name)
    kinematic=json.loads((ROOT/audit['specification']['input_audit']).read_text())
    concerns=[r for r in audit['rows'] if any(e['original_settled'] and not e['alternative_settled'] for e in r['lane_change_settling'])]
    fig,axes=plt.subplots(1,len(concerns),figsize=(5*len(concerns),6),squeeze=False);details=[]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    for axis,row in zip(axes.flat,concerns):
        folder=ROOT/'runs'/row['run'];screen=json.loads((folder/'anchored_feasibility.json').read_text());conv=json.loads((ROOT/'samples'/screen['summary']['sample']/'conversion.json').read_text())
        center=np.load(folder/'internal_0000.npz')['center'];points=np.vstack([center[:2],np.load(folder/'refined_v2_candidates.npz')['world_xy'][row['candidate']-1]])
        angles=headings(points,float(center[6]));dense,_=interpolate_centers_and_angles(points,angles)
        inverse=inverse_center_path(dense,float(center[6]),**kinematic['geometry'],dt=.05)['heading'][::2]
        graph,_=add_parallel_connector_edges(load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']))
        event=next(e for e in row['lane_change_settling'] if e['original_settled'] and not e['alternative_settled']);target=graph.forward_corridor(event['to'])
        length=float(center[3]);width=float(center[4]);bad=[i for i in range(len(points)-6,len(points)) if not target.covers(footprint(points[i],inverse[i],length,width))]
        step=max(bad,key=lambda i:footprint(points[i],inverse[i],length,width).difference(target).area)
        old=footprint(points[step],angles[step],length,width);new=footprint(points[step],inverse[step],length,width)
        if not target.covers(old):raise ValueError('Expected original body to be settled')
        angle=float(angles[step]);rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        local=lambda p:(np.asarray(p)[...,:2]-points[step])@rotation
        polys=[target] if target.geom_type=='Polygon' else list(target.geoms)
        for poly in polys:
            xy=local(poly.exterior.coords);axis.fill(xy[:,0],xy[:,1],color='#e3eee7',alpha=.85);axis.plot(xy[:,0],xy[:,1],color='#7c9d8c',lw=1)
        for shape,color in [(old,'#147e83'),(new,'#b33f45')]:
            xy=local(shape.exterior.coords);axis.plot(xy[:,0],xy[:,1],color=color,lw=2)
        outside=new.difference(target);parts=[outside] if outside.geom_type=='Polygon' else list(outside.geoms)
        for poly in parts:
            if poly.geom_type=='Polygon':
                xy=local(poly.exterior.coords);axis.fill(xy[:,0],xy[:,1],color='#b33f45',alpha=.5)
        axis.scatter([0],[0],s=18,color='#183047');axis.set_xlim(-3.2,3.2);axis.set_ylim(-2,2);axis.set_aspect('equal');axis.grid(alpha=.18)
        axis.set_xlabel('Forward relative to original heading (m)');axis.set_ylabel('Left (m)')
        degrees=abs(float(np.degrees(np.arctan2(np.sin(inverse[step]-angles[step]),np.cos(inverse[step]-angles[step])))))
        corner_distance=max(Point(p).distance(target) for p in new.exterior.coords)
        axis.set_title(f'{row["run"].rsplit("/",1)[-1]} · #{row["candidate"]}\nt = {step*.1:.1f} s, heading difference {degrees:.2f}°\nFarthest corner outside: {corner_distance*1000:.1f} mm',fontsize=10)
        details.append({'run':row['run'],'candidate':row['candidate'],'time_seconds':step*.1,'heading_difference_deg':degrees,
            'outside_area_m2':float(outside.area),'maximum_vertex_outside_m':float(corner_distance),'outside_sample_times_seconds':[i*.1 for i in bad]})
    fig.suptitle('Small heading changes reveal fragile lane-change completion',fontsize=17,fontweight='bold',x=.04,ha='left',y=.97)
    fig.text(.04,.90,'Identical body-center points and dimensions; only the heading assumption changes. Green shading = target corridor.',fontsize=11)
    fig.legend(handles=[Line2D([],[],color='#147e83',lw=2,label='Original tangent heading'),Line2D([],[],color='#b33f45',lw=2,label='Inverse-bicycle heading')],loc='lower center',bbox_to_anchor=(.5,.12),ncol=2,frameon=False)
    fig.text(.04,.075,'All 39 prior road/collision checks reproduced; alternative headings caused 0 road failures, 0 CV collisions, but 3 lost target settling.',fontsize=10)
    fig.text(.04,.035,'These are diagnostic assumptions, not ground truth. This finding does not establish actuator feasibility, legal crossing or closed-loop success.',fontsize=9,color='#677987')
    fig.subplots_adjust(left=.055,right=.98,top=.83,bottom=.24,wspace=.28)
    dest=ROOT/'runs/project-v2/reports';fig.savefig(dest/'heading-sensitivity.png',dpi=180);fig.savefig(dest/'heading-sensitivity.pdf');plt.close(fig)
    write_json(source.with_name('report-summary.json'),{'source_sha256':sha256(source),'generator_sha256':sha256(__file__),'summary':audit['summary'],'illustrated_failures':details})
    print(json.dumps({'summary':audit['summary'],'illustrated_failures':details},indent=2))


if __name__=='__main__':main()
