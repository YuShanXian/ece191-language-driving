"""Show why connector entry and front/body stop-region contact are different events."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.affinity import translate,rotate
from matplotlib.patches import Patch
from audit_stop_regions import layers
from evaluate_candidate_checks import load_graph
from trajectory_checks import headings,footprint
from mtr_project.pose_geometry import interpolate_centers_and_angles
from mtr_project.paths import ROOT,sha256,write_json


COLORS={'center':'#277da8','front_edge':'#d08a29','body':'#65856a'}


def first_event(contact):
    return 'already intersects at t=0' if contact['intersects_at_anchor'] else contact['first_later_contact_interval_s']


def main():
    folder=ROOT/'runs/project-v2/stop-region-geometry-v1';path=folder/'audit.json';audit=json.loads(path.read_text())
    verification=folder/'verification.json'
    if json.loads(verification.read_text())['audit_sha256']!=sha256(path):raise ValueError('Unverified stop-region audit')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(14,10),gridspec_kw={'height_ratios':[1.5,1]},layout=None)
    examples=[]
    for column,(key,sid) in enumerate([('turn-01-t040975582','63101'),('turn-00-t027100806','64546')]):
        w=next(w for w in audit['windows'] if w['window']['key']==key);window=w['window'];c=next(c for c in w['candidates'] if c['candidate']==9)
        v=next(v for v in c['connector_visits'] if any(a['id']==sid for a in v.get('raw_associations',[])))
        region=next(a for a in v['raw_associations'] if a['id']==sid)
        conv=json.loads((ROOT/'samples'/window['sample']/'conversion.json').read_text());run=ROOT/'runs'/window['run']
        center=np.load(run/'internal_0000.npz')['center'];xy=np.load(run/'refined_v2_candidates.npz')['world_xy'][8]
        points=np.vstack((center[:2],xy));dense,angles=interpolate_centers_and_angles(points,headings(points,float(center[6])))
        origin=np.asarray(conv['origin_xy_m']);data=layers(ROOT/conv['source_map'],conv['source_epsg'])
        polygon=translate(data['stop_polygons'].loc[sid].geometry,-origin[0],-origin[1]);graph=load_graph(origin,conv['source_epsg'],conv['source_map'])
        def ego_geometry(shape):return rotate(translate(shape,-float(center[0]),-float(center[1])),-float(center[6]),origin=(0,0),use_radians=True)
        h=float(center[6]);rotation=np.array([[np.cos(h),np.sin(h)],[-np.sin(h),np.cos(h)]])
        relative=(dense-center[:2])@rotation.T;ax=axes[0,column]
        for node in graph.nodes.values():
            shape=ego_geometry(node.polygon)
            if shape.geom_type=='Polygon':ax.plot(*shape.exterior.xy,color='#bcc8d0',lw=.6,zorder=0)
        stop=ego_geometry(polygon);ax.fill(*stop.exterior.xy,color='#e6b75b',alpha=.5,label='Associated stop polygon')
        ax.plot(relative[:,0],relative[:,1],color=COLORS['center'],lw=2,label='Candidate center path')
        first=region['sampled_contacts']['front_edge']['runs'][0]['first_sample_time_s']
        stamps=sorted(set([0.,first,6.]))
        for t in stamps:
            i=round(t/.05);body=ego_geometry(footprint(dense[i],angles[i],float(center[3]),float(center[4])))
            ax.plot(*body.exterior.xy,color='#263d50',lw=1.3,ls='-' if t==0 else '--')
            ax.text(relative[i,0]+.15,relative[i,1]+.3,f'{t:g}s',fontsize=8)
        ax.set_aspect('equal',adjustable='datalim');ax.set_xlim(relative[:,0].min()-4,relative[:,0].max()+4)
        ax.set_ylim(relative[:,1].min()-4,relative[:,1].max()+4);ax.grid(alpha=.15)
        ax.set_xlabel('Forward from observed pose (m)');ax.set_ylabel('Left from observed pose (m)')
        if column==0:ax.set_title('Current red / candidate 9\nFront edge already overlaps stop polygon at t=0',fontsize=11)
        else:ax.set_title('Partial left turn / candidate 9\nRaw TURN_STOP association; current signal unobserved',fontsize=11)
        ax.legend(fontsize=8,loc='upper left')
        timeline=axes[1,column];timeline.set_xlim(0,6);timeline.set_xlabel('Elapsed time (s)');timeline.grid(axis='x',alpha=.2)
        relevant=[r for r in w['candidates'] if r['candidate'] in ([9,14,51] if column==0 else [9])]
        yt=[];labels=[];counter=0
        for r in relevant:
            vr=next(v for v in r['connector_visits'] if any(a['id']==sid for a in v.get('raw_associations',[])))
            rr=next(a for a in vr['raw_associations'] if a['id']==sid)
            for kind in ['front_edge','center','body']:
                yt.append(counter);labels.append(f'q{r["candidate"]} {kind.replace("_"," ")}')
                for interval in rr['sampled_contacts'][kind]['runs']:
                    start=interval['first_sample_time_s'];end=interval['last_sample_time_s']
                    timeline.plot([start,end],[counter,counter],color=COLORS[kind],lw=5,solid_capstyle='butt')
                    timeline.scatter([start,end],[counter,counter],color=COLORS[kind],s=12)
                counter+=1
            examples.append(dict(window=key,candidate=r['candidate'],connector=vr['connector_id'],region=sid,
                current_signal=vr['current_signal']['classification'],official_traffic_light_stop_selection=rr['official_traffic_light_stop_selection'],
                center_node_entry_interval=vr['center_node_transition_interval_s'],
                first_contacts={kind:first_event(rr['sampled_contacts'][kind]) for kind in COLORS}))
        timeline.set_yticks(yt,labels,fontsize=8);timeline.invert_yaxis()
        timeline.set_title('Recorded sampled-contact intervals (0.05 s grid)',fontsize=10)
    fig.suptitle('A road connection is not a stop-line crossing',fontsize=19,fontweight='bold',x=.04,ha='left')
    fig.text(.04,.936,'All 62 baseline-passing candidates audited; two diagnostic examples shown. Candidate geometry, not simulated vehicle motion.',fontsize=10)
    fig.text(.04,.045,'39 raw association occurrences; 10 retained by official traffic-light stop selection. Center/front/body contacts: 4 / 4 / 11.',fontsize=10)
    fig.text(.04,.022,'Boundary touch counts. Current color is not arrival color. Region overlap does not establish a legal crossing, stopping duty or permission.',fontsize=9,color='#596570')
    fig.subplots_adjust(left=.1,right=.97,top=.86,bottom=.11,hspace=.45,wspace=.35)
    report=ROOT/'runs/project-v2/reports'
    for suffix in ['png','pdf']:fig.savefig(report/('stop-region-geometry.'+suffix),dpi=180)
    plt.close(fig)
    summary=dict(audit_sha256=sha256(path),verification_sha256=sha256(verification),counts=audit['counts'],examples=examples,scope=audit['scope'])
    write_json(folder/'report-summary.json',summary);print(json.dumps(summary['examples'],indent=2))


if __name__=='__main__':main()
