"""Evaluate cached real MTR candidates using present observations and map only."""
import argparse,json,pickle,sqlite3
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.affinity import translate
from pyproj import Transformer
from trajectory_checks import RoadGraph,RoadNode,motion_check,collision_check
from refine_candidate_paths import refine

ROOT=Path(__file__).resolve().parent.parent

def load_graph(origin,epsg,map_path=None):
    p=Path(map_path) if map_path else ROOT/'data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg'
    if not p.is_absolute():p=ROOT/p
    transform=Transformer.from_crs(epsg,4326,always_xy=True)
    corners=[transform.transform(*(origin+[x,y])) for x in [-300,300] for y in [-300,300]]
    bbox=(min(q[0] for q in corners),min(q[1] for q in corners),max(q[0] for q in corners),max(q[1] for q in corners))
    def read(layer):return gpd.read_file(p,layer=layer,bbox=bbox,fid_as_index=True).to_crs(epsg=epsg)
    lanes=read('lanes_polygons');conn=read('gen_lane_connectors_scaled_width_polygons');links=read('lane_connectors');baselines=read('baseline_paths')
    lines={}
    for _,r in baselines.iterrows():
        if r.geometry.geom_type!='LineString':continue
        if pd.notna(r.lane_fid):key='L'+str(int(r.lane_fid))
        elif pd.notna(r.lane_connector_fid):key='C'+str(int(r.lane_connector_fid))
        else:continue
        lines[key]=translate(r.geometry,-origin[0],-origin[1])
    nodes=[];edges={}
    for _,r in lanes.iterrows():
        key='L'+str(int(r.lane_fid))
        if key not in lines:continue
        nodes.append(RoadNode(key,translate(r.geometry,-origin[0],-origin[1]),lines[key],
                              'lane',int(r.lane_group_fid),int(r.lane_index)))
    for _,r in conn.iterrows():
        key='C'+str(int(r.lane_connector_fid))
        if key in lines:nodes.append(RoadNode(key,translate(r.geometry,-origin[0],-origin[1]),lines[key],'connector'))
    keys={n.key for n in nodes}
    def add(a,b,relation):
        if a in keys and b in keys:edges.setdefault(a,{})[b]=relation
    for fid,r in links.iterrows():
        add('L'+str(int(r.exit_lane_fid)),'C'+str(int(fid)),'forward')
        add('C'+str(int(fid)),'L'+str(int(r.entry_lane_fid)),'forward')
    for _,group in lanes.groupby('lane_group_fid'):
        for _,a in group.iterrows():
            for _,b in group.iterrows():
                if abs(a.lane_index-b.lane_index)==1:
                    add('L'+str(int(a.lane_fid)),'L'+str(int(b.lane_fid)),
                        'left' if b.lane_index<a.lane_index else 'right')
    return RoadGraph(nodes,edges)

def current_obstacles(conversion):
    from mtr_project.sources import source_database
    db=source_database(conversion)
    c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    query='''SELECT b.*,cat.name AS category FROM lidar_box b JOIN lidar_pc pc ON b.lidar_pc_record_id=pc.record_id
        JOIN track tr ON b.track_record_id=tr.record_id JOIN category cat ON tr.category_record_id=cat.record_id WHERE pc.timestamp=?'''
    origin=np.asarray(conversion['origin_xy_m']);result=[];bad=[]
    for r in c.execute(query,(conversion['current_timestamp_us'],)):
        values=[r['x'],r['y'],r['yaw'],r['width'],r['length']]
        if not all(v is not None and np.isfinite(v) for v in values) or min(r['width'],r['length'])<=0:
            bad.append(r['track_record_id'].hex());continue
        xy=np.asarray([r['x'],r['y']])-origin
        velocity=np.array([r['vx'],r['vy']],dtype=float) if r['category'] in ('vehicle','pedestrian','bicycle') else np.zeros(2)
        if not np.isfinite(velocity).all():bad.append(r['track_record_id'].hex());continue
        result.append({'id':r['track_record_id'].hex(),'category':r['category'],'xy':xy.tolist(),
                       'velocity':velocity.tolist(),'heading':r['yaw'],'length':r['length'],'width':r['width']})
    c.close();return result,bad

def evaluate(sample,run,refined=False,boundary_acceleration=False):
    sample_dir=ROOT/'samples'/sample;out=ROOT/'runs'/run
    conv=json.loads((sample_dir/'conversion.json').read_text())
    graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv.get('source_map'))
    obstacles,bad=current_obstacles(conv)
    data=np.load(out/'internal_0000.npz');center=data['center']
    initial_acceleration=None
    if boundary_acceleration:
        assert refined
        with (sample_dir/conv['scenario']).open('rb') as f:scenario=pickle.load(f)
        velocities=scenario['tracks']['ego']['state']['velocity'][17:21]
        initial_acceleration=np.diff(velocities,axis=0).mean(axis=0)/.1
    results=[];derived=[]
    for i,(xy,score) in enumerate(zip(data['world_xy'],data['scores'])):
        points=np.vstack([center[:2],xy]).astype(float)
        refinement=None
        if refined:points,refinement=refine(points,center[7:9],initial_acceleration=initial_acceleration)
        derived.append(points[1:])
        route=graph.match(points,float(center[6]))
        graph.settled_lane_changes(route,points,float(center[6]),float(center[3]),float(center[4]))
        body=graph.body_check(points,float(center[6]),float(center[3]),float(center[4]))
        motion=motion_check(points,center[7:9],initial_acceleration=initial_acceleration)
        collision=collision_check(points,float(center[6]),float(center[3]),float(center[4]),obstacles)
        reasons=[]
        if not route['matched']:reasons.append('road_route')
        if not body['passed']:reasons.append('road_footprint')
        if not motion['passed']:reasons.append('motion')
        if not collision['passed']:reasons.append('constant_velocity_collision')
        if bad:reasons.append('incomplete_obstacles')
        if refinement and not refinement['within_deviation_bound']:reasons.append('refinement_deviation')
        results.append({'candidate':i+1,'score':float(score),'in_original_five':bool(i in data['selected_indices']),
                        'passes_current_checks':not reasons,'rejected_by':reasons,
                        'route':route,'body':body,'motion':motion,'collision':collision,'refinement':refinement})
    summary={'sample':sample,'run':run,'candidates':len(results),'present_obstacles':len(obstacles),
             'invalid_obstacles':bad,'passed_candidates':[r['candidate'] for r in results if r['passes_current_checks']],
             'rejection_counts':dict(Counter(x for r in results for x in r['rejected_by'])),
             'matched_lane_change_candidates':[r['candidate'] for r in results if r['route'].get('lane_changes')],
             'matched_turn_candidates':[r['candidate'] for r in results if r['route'].get('turns')],
             'scope':'Offline screening, not a safety guarantee. Present obstacles extrapolated at constant velocity; static boxes included. Traffic lights, lane-marking legality, occluded actors and interactive response not modeled.'}
    summary['prediction_source']='bounded_refinement_of_MTR' if refined else 'raw_MTR'
    summary['geometry_version']='central_tangent_v2'
    summary['initial_acceleration_from_past_only']=None if initial_acceleration is None else initial_acceleration.tolist()
    name='refined_feasibility' if refined else 'feasibility'
    if boundary_acceleration:name='refined_v2_feasibility'
    (out/(name+'.json')).write_text(json.dumps({'summary':summary,'candidates':results},indent=2))
    if refined:np.savez_compressed(out/('refined_v2_candidates.npz' if boundary_acceleration else 'refined_candidates.npz'),world_xy=np.asarray(derived),scores=data['scores'])
    print(json.dumps(summary,indent=2),flush=True)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sample');p.add_argument('--run');p.add_argument('--refined',action='store_true');p.add_argument('--boundary-acceleration',action='store_true');args=p.parse_args()
    cases=[(args.sample,args.run)] if args.sample and args.run else [('nuplan-one','internal-stopped'),('nuplan-moving','internal-moving'),('nuplan-lane','internal-lane')]
    for sample,run in cases:evaluate(sample,run,args.refined,args.boundary_acceleration)
