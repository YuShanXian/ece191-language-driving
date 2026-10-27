"""Inspect a missed maneuver near map connectors, without changing the detector."""
import json,sqlite3
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import Point
from evaluate_candidate_checks import load_graph
from mtr_project.paths import ROOT,sha256,write_json


def main():
    source=ROOT/'runs/project-v2/replay/doplan_006160-window-v2.json'
    replay=json.loads(source.read_text());trace=replay['trace']
    subset=[r for r in trace if 190<=r['seconds_from_first_lidar']<=203]
    origin=np.array(subset[0]['xy']);heading=subset[0]['heading']
    rotation=np.array([[np.cos(heading),-np.sin(heading)],[np.sin(heading),np.cos(heading)]])
    db=ROOT/'data/nuplan/db'/f'{replay["source_clip"]}.db'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as connection:
        epsg=connection.execute('SELECT epsg FROM ego_pose LIMIT 1').fetchone()[0]
    graph=load_graph(origin,epsg)
    dest=ROOT/'runs/project-v2/replay-diagnostics/doplan_006160';dest.mkdir(parents=True,exist_ok=True)
    transitions=[];previous=None
    for row in trace:
        node=row['localization']['node']
        if previous is None or node!=previous['localization']['node']:
            before=None if previous is None else previous['localization']['node']
            info=graph.nodes.get(node)
            transitions.append({'seconds':row['seconds_from_first_lidar'],'from':before,'to':node,
                'direct_relation':graph.edges.get(before,{}).get(node),'reason':row['localization']['reason'],
                'node_kind':info.kind if info else None,'lane_group':info.lane_group if info else None,
                'lane_index':info.lane_index if info else None,
                'outgoing':graph.edges.get(node,{})})
        previous=row
    xy=(np.array([r['xy'] for r in subset])-origin)@rotation
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(12,5.8))
    for key,node in graph.nodes.items():
        if node.polygon.distance(Point(np.mean(xy,axis=0)@rotation.T))>150:continue
        polygons=[node.polygon] if node.polygon.geom_type=='Polygon' else list(node.polygon.geoms)
        for polygon in polygons:
            points=np.asarray(polygon.exterior.coords)@rotation
            ax.plot(points[:,0],points[:,1],color='#ccd5df',lw=.7,zorder=1)
        if key in {r['localization']['node'] for r in subset}:
            points=np.asarray(node.baseline.coords)@rotation
            ax.plot(points[:,0],points[:,1],color='#9fb4c6',lw=1.1,alpha=.7)
            mid=points[len(points)//2]
            if -8<mid[0]<170 and -14<mid[1]<14:ax.annotate(key,mid,fontsize=7,color='#718397')
    ax.plot(xy[:,0],xy[:,1],color='#147e83',lw=2.4,label='Recorded ego center')
    uncertain=np.array([r['localization']['node'] is None for r in subset])
    ax.scatter(xy[uncertain,0],xy[uncertain,1],s=35,color='#c36a49',zorder=4,label='Localization unavailable')
    for second in [190,195,196.6,198.3,202]:
        idx=int(np.argmin([abs(r['seconds_from_first_lidar']-second) for r in subset]))
        ax.annotate(f'{subset[idx]["seconds_from_first_lidar"]:.1f} s',xy[idx],xytext=(0,17),textcoords='offset points',ha='center',fontsize=9,
                    arrowprops={'arrowstyle':'-','color':'#64768a'})
    ax.set_xlim(-8,175);ax.set_ylim(-17,17);ax.set_aspect('equal',adjustable='box')
    ax.set_xlabel('Forward from the 190 s pose (m)');ax.set_ylabel('Left (m)');ax.grid(alpha=.15)
    ax.legend(loc='lower left',frameon=False);ax.set_title('Actual doPlan annotation: right merge — current detector remains unresolved')
    fig.text(.08,.05,'Map connector transition loses localization near 196.6 s. Recorded path is shown for diagnosis only.\nThis figure does not establish maneuver truth or evaluate an executed MTR plan.',fontsize=9,color='#64768a')
    fig.tight_layout(rect=[0,.12,1,.98]);fig.savefig(dest/'connector-transition.png',dpi=180);fig.savefig(dest/'connector-transition.pdf');plt.close(fig)
    evidence={'replay':str(source.relative_to(ROOT)),'replay_sha256':sha256(source),
              'diagnostic_interval_seconds':[190,203],'transitions':transitions,
              'unknown_node_samples':sum(r['localization']['node'] is None for r in trace),
              'scope':'Read-only diagnostic. No thresholds changed and no maneuver label inferred solely from this plot.',
              'script_sha256':sha256(Path(__file__))}
    write_json(dest/'connector-transition.json',evidence)
    print(json.dumps([r for r in transitions if 190<=r['seconds']<=203],indent=2))


if __name__=='__main__':main()
