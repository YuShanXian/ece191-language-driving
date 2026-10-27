"""Map-grounded candidate inspection. Geometry screening, NOT safety validation."""
import json,csv,pickle
from pathlib import Path
from collections import Counter
import numpy as np
import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parent.parent
mapfile=root/'data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg'
summaries=[]
cases=[('nuplan-moving','internal-moving','nuplan-moving'),('nuplan-one','internal-stopped','nuplan-first')]
if (root/'runs/internal-lane/internal_0000.npz').exists():cases.append(('nuplan-lane','internal-lane',None))
for sample,run,old in cases:
    out=root/'runs'/run;data=np.load(out/'internal_0000.npz')
    conversion=json.loads((root/'samples'/sample/'conversion.json').read_text())
    origin=np.array(conversion['origin_xy_m']);epsg=conversion['source_epsg']
    center=data['center'];a=center[6];rotation=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
    def local(xy): return (np.asarray(xy)[:,:2]-origin)@rotation
    to_ll=Transformer.from_crs(epsg,4326,always_xy=True)
    corners=[to_ll.transform(*(origin+[x,y])) for x in [-250,250] for y in [-250,250]]
    bbox=(min(p[0] for p in corners),min(p[1] for p in corners),max(p[0] for p in corners),max(p[1] for p in corners))
    lanes=gpd.read_file(mapfile,layer='lanes_polygons',bbox=bbox).to_crs(epsg=epsg)
    baselines=gpd.read_file(mapfile,layer='baseline_paths',bbox=bbox).to_crs(epsg=epsg)
    covering=lanes[lanes.geometry.covers(Point(origin))]
    connectors=gpd.read_file(mapfile,layer='gen_lane_connectors_scaled_width_polygons',bbox=bbox).to_crs(epsg=epsg)
    connector_hits=connectors[connectors.geometry.covers(Point(origin))]
    links=gpd.read_file(mapfile,layer='lane_connectors',bbox=bbox,fid_as_index=True).to_crs(epsg=epsg)
    current=covering.iloc[0] if len(covering)==1 else None
    if current is not None:
        group=lanes[lanes.lane_group_fid==current.lane_group_fid]
        neighbors=group[abs(group.lane_index-current.lane_index)==1]
        current_geom=current.geometry
    else:
        assert len(connector_hits)>0, 'Neither ordinary lane nor connector matched'
        neighbors=lanes.iloc[:0]
        current_geom=unary_union(connector_hits.geometry.tolist())
    def lane_ids(p):return lanes.loc[lanes.geometry.covers(Point(p)),'lane_fid'].astype(int).tolist()
    rows=[]
    for i,(p,score) in enumerate(zip(data['world_xy']+origin,data['scores'])):
        end_ids=lane_ids(p[-1]);disp=p[-1]-p[-11]
        heading_delta=float(np.degrees(np.arctan2((disp@rotation)[1],(disp@rotation)[0]))) if np.linalg.norm(disp)>.5 else None
        localp=data['local_xy'][i];label='no_verified_turn_or_lane_change'
        neighbor_id=None;direction=None
        for _,neighbor in neighbors.iterrows():
            if int(neighbor.lane_fid) not in end_ids:continue
            # Last 0.5 s remains in the neighboring lane, and every sampled center is in these two lanes.
            union=unary_union([current.geometry,neighbor.geometry]).buffer(.05)
            if all(neighbor.geometry.covers(Point(q)) for q in p[-5:]) and union.covers(LineString(np.vstack([origin,p]))):
                lane_line=baselines[baselines.lane_fid==neighbor.lane_fid]
                aligned=False
                for line in lane_line.geometry:
                    d=line.project(Point(p[-1]));v=np.array(line.interpolate(min(line.length,d+1)).coords[0])-np.array(line.interpolate(max(0,d-1)).coords[0])
                    if np.linalg.norm(disp)>.5 and np.linalg.norm(v)>0:
                        aligned=np.dot(v,disp)/np.linalg.norm(v)/np.linalg.norm(disp)>np.cos(np.radians(20))
                if aligned:
                    direction='right' if neighbor.lane_index>current.lane_index else 'left'
                    neighbor_id=int(neighbor.lane_fid);label=f'{direction}_lane_change_geometry'
        if heading_delta is not None and abs(heading_delta)>=30 and np.linalg.norm(p[-1]-origin)>5 and neighbor_id is None:
            label='reverse_or_uturn_shape_unverified' if abs(heading_delta)>=150 else 'turn_shaped_unverified_connectivity'
        # A conservative single-connector turn test: ordered traversal of a source lane,
        # its directed connector, and its destination lane, with center path inside their union.
        verified_turn=False
        if current is not None and heading_delta is not None and 30<=abs(heading_delta)<150:
            outgoing=links[links.exit_lane_fid==current.lane_fid]
            for fid,link in outgoing.iterrows():
                if int(link.entry_lane_fid) not in end_ids:continue
                destlane=lanes[lanes.lane_fid==link.entry_lane_fid]
                connpoly=connectors[connectors.lane_connector_fid==int(fid)]
                if len(destlane)!=1 or len(connpoly)!=1:continue
                corridor=unary_union([current.geometry,destlane.iloc[0].geometry,connpoly.iloc[0].geometry]).buffer(.05)
                if not corridor.covers(LineString(np.vstack([origin,p]))):continue
                dst=destlane.iloc[0].geometry
                if not all(dst.covers(Point(q)) for q in p[-5:]):continue
                cl=baselines[baselines.lane_fid==link.entry_lane_fid]
                for line in cl.geometry:
                    distance=line.project(Point(p[-1]))
                    tangent=np.array(line.interpolate(min(line.length,distance+1)).coords[0])-np.array(line.interpolate(max(0,distance-1)).coords[0])
                    if np.linalg.norm(tangent)>0 and np.dot(tangent,disp)/np.linalg.norm(tangent)/np.linalg.norm(disp)>np.cos(np.radians(20)):
                        verified_turn=True
                if verified_turn:label='connected_turn_centerline_geometry'
        velocities=np.diff(np.vstack([center[:2],data['world_xy'][i]]),axis=0)/.1
        accelerations=np.diff(np.vstack([center[7:9],velocities]),axis=0)/.1
        rows.append({'candidate':i+1,'score':float(score),'selected_in_five':bool(i in data['selected_indices']),
            'end_forward_m':float(localp[-1,0]),'end_left_m':float(localp[-1,1]),
            'max_abs_left_m':float(abs(localp[:,1]).max()),'final_heading_delta_deg':heading_delta,
            'end_lane_ids':end_ids,'neighbor_lane_id':neighbor_id,'label':label})
        rows[-1]['max_acceleration_mps2']=float(np.linalg.norm(accelerations,axis=1).max())
        rows[-1]['connected_turn_geometry']=verified_turn
    if old:
        previous=np.load(root/'runs'/old/'prediction_0000.npz')
        rerun=np.load(out/'prediction_0000.npz')
        assert np.allclose(previous['trajectories'],rerun['trajectories'],atol=1e-4)
    summary={'sample':sample,'candidate_count':len(rows),'current_lane_id':int(current.lane_fid) if current is not None else None,
        'current_lane_index':int(current.lane_index) if current is not None else None,'current_lane_group':int(current.lane_group_fid) if current is not None else None,
        'current_connector_ids':connector_hits.lane_connector_fid.astype(int).tolist(),
        'lane_change_test_applicable':current is not None,
        'neighbor_ids':neighbors.lane_fid.astype(int).tolist(),'counts':dict(Counter(r['label'] for r in rows)),
        'max_abs_left_m':max(r['max_abs_left_m'] for r in rows),
        'original_five_unchanged':True if old else None,
        'limitations':['Geometry screen only; no footprint, collision, marking legality or dynamics checks.',
            'Turn-shaped means geometric direction change, not verified road-connected turn.',
            'Lane change requires immediate same-group neighbor, stable endpoint, connected center path, and aligned direction.',
            'Same-segment lane-change test can miss changes that finish beyond a connector; zero matches is not proof of absence.',
            'Negative result is limited to these sampled times and this 6-second horizon.']}
    (out/'maneuvers.json').write_text(json.dumps({'summary':summary,'candidates':rows},indent=2))
    with (out/'candidate_table.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    fig,axes=plt.subplots(2,1,figsize=(12,8),constrained_layout=True)
    for ax in axes:
        for _,r in lanes.iterrows():
            if r.geometry.geom_type=='Polygon':
                q=local(r.geometry.exterior.coords);ax.plot(*q.T,color='#d6dce3',lw=.7)
        for line in baselines.geometry:
            if line.geom_type=='LineString':q=local(line.coords);ax.plot(*q.T,color='#e7ebef',lw=.5,ls=':')
        for part in ([current_geom] if current_geom.geom_type=='Polygon' else current_geom.geoms):
            q=local(part.exterior.coords);ax.plot(*q.T,color='#777777',lw=1.4,label='Current lane / connector boundary')
        for p in data['local_xy']:ax.plot(*p.T,color='#4b83bd',alpha=.25,lw=.9)
        for j,i in enumerate(data['selected_indices']):
            ax.plot(*data['local_xy'][i].T,lw=1.8,label=f'Final {j+1}: query {i+1}')
        ax.scatter(0,0,c='black',s=20);ax.set_xlabel('Forward (m)');ax.set_ylabel('Left (m)');ax.grid(alpha=.15)
    points=data['local_xy'].reshape(-1,2)
    axes[0].set_xlim(min(-5,points[:,0].min()-3),points[:,0].max()+5)
    axes[0].set_ylim(min(-6,points[:,1].min()-2),max(6,points[:,1].max()+2));axes[0].set_aspect('equal')
    axes[0].set_title('Map view, equal distance scale');axes[0].legend(loc='center left',bbox_to_anchor=(1.01,.5),fontsize=8)
    axes[1].set_xlim(axes[0].get_xlim());axes[1].set_ylim(-5,5)
    axes[1].set_title('Lateral detail (axes have different scales; not a steering-angle plot)')
    fig.suptitle(f'{sample}: all {len(rows)} decoder candidates before final selection\nBlue: all candidates; colored: original final five; geometry screen only')
    fig.savefig(out/'all-candidates.png',dpi=150,bbox_inches='tight');plt.close(fig)
    summaries.append(summary)
print(json.dumps(summaries,indent=2))
