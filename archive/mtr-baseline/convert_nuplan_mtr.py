"""Single-clip experimental nuPlan -> Valeo4Cast ScenarioNet adapter.
Uses ground-truth tracked boxes, not AV2 tracker outputs. No language conditioning.
"""
import argparse,csv,json,pickle,sqlite3
from pathlib import Path
import numpy as np
import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point
from nuplan.database.nuplan_db.nuplan_scenario_queries import get_ego_state_for_lidarpc_record_id_from_db

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--gps-row',type=int)
parser.add_argument('--db',type=Path,help='Exact nuPlan DB; requires --seconds or --timestamp-us')
parser.add_argument('--map',type=Path,help='Vector map override')
anchors=parser.add_mutually_exclusive_group()
anchors.add_argument('--seconds',type=float,help='Seconds after first LiDAR observation')
anchors.add_argument('--timestamp-us',type=int,help='Exact LiDAR timestamp')
parser.add_argument('--output',default='samples/nuplan-one')
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
clip='2021.06.09.12.39.51_veh-26_05332_05540'
db=args.db or root/f'data/nuplan/db/{clip}.db'
if not db.is_absolute():db=root/db
db=db.resolve();clip=db.stem
dest=root/args.output
if dest.exists():parser.error(f'Output already exists: {dest}')
if args.db and args.seconds is None and args.timestamp_us is None:
    parser.error('Explicit DB requires --seconds or --timestamp-us; GPS from another log is never reused')
if args.gps_row is not None and (args.seconds is not None or args.timestamp_us is not None):
    parser.error('GPS row cannot be combined with another anchor')
c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True); c.row_factory=sqlite3.Row
all_frames=list(c.execute('SELECT record_id,timestamp,ego_pose_record_id FROM lidar_pc ORDER BY timestamp'))
if not all_frames:parser.error('No LiDAR observations')
if args.timestamp_us is not None:
    matches=[i for i,r in enumerate(all_frames) if r['timestamp']==args.timestamp_us]
    if not matches:parser.error('Timestamp is not an exact LiDAR observation')
    anchor_i=matches[0];anchor_basis='explicit_lidar_timestamp'
elif args.seconds is not None:
    if not np.isfinite(args.seconds) or args.seconds<0:parser.error('Invalid --seconds')
    requested=all_frames[0]['timestamp']+round(args.seconds*1e6)
    anchor_i=min(range(len(all_frames)),key=lambda i:abs(all_frames[i]['timestamp']-requested))
    if abs(all_frames[anchor_i]['timestamp']-requested)>30000:parser.error('Anchor outside timestamp coverage/tolerance')
    anchor_basis='seconds_after_first_lidar_nearest_30ms'
else:
    if args.gps_row is None:args.gps_row=500
    with (root/'references/sample_gps.csv').open() as f:gps=list(csv.DictReader(f))
    if not 0<=args.gps_row<len(gps):parser.error('GPS row out of range')
    anchor=int(gps[args.gps_row]['timestamp_us'])
    anchor_i=next(i for i,r in enumerate(all_frames) if r['timestamp']==anchor)
    anchor_basis='legacy_sample_gps_row'
anchor=all_frames[anchor_i]['timestamp']
indices=np.arange(anchor_i-40,anchor_i+121,2)
if indices[0]-2<0 or indices[-1]>=len(all_frames):
    parser.error('Need 2.1 seconds past and 6 seconds future for offline evaluation sample')
frames=[all_frames[i] for i in indices]
ts=np.array([r['timestamp'] for r in frames],dtype=np.int64)
assert len(frames)==81 and np.max(np.abs(np.diff(ts)/1e6-.1))<.002
egos=[get_ego_state_for_lidarpc_record_id_from_db(str(db),r['record_id'].hex()) for r in frames]
center=np.array([egos[20].center.x,egos[20].center.y])
epsg=c.execute('SELECT epsg FROM ego_pose WHERE record_id=?',(frames[20]['ego_pose_record_id'],)).fetchone()[0]
tracks={}
def track(key,kind,label,klass):
    if key not in tracks:
        tracks[key]={'type':kind,'object_label':label,'object_class':klass,
            'metadata':{'object_id':key,'type':kind,'track_length':81,'dataset':'nuplan'},
            'state':{k:np.zeros(shape,dtype=np.float32) for k,shape in
                     [('position',(81,3)),('heading',(81,)),('velocity',(81,2)),
                      ('length',(81,)),('width',(81,)),('height',(81,)),('valid',(81,)),('tracking_scores',(81,))]}}
        tracks[key]['state']['timestamps']=ts*1000 # same ns convention as AV2 adapter
    return tracks[key]['state']
ego=track('ego','VEHICLE',0,'REGULAR_VEHICLE')
for i,e in enumerate(egos):
    ego['position'][i,:2]=np.array([e.center.x,e.center.y])-center
    ego['heading'][i]=e.center.heading
    for k in ['length','width','height']: ego[k][i]=getattr(e.car_footprint,k)
    ego['valid'][i]=1; ego['tracking_scores'][i]=1
# Backward position differences use only past observations; no future leakage.
previous=get_ego_state_for_lidarpc_record_id_from_db(str(db),all_frames[indices[0]-2]['record_id'].hex())
xy=np.array([[previous.center.x,previous.center.y]]+[[e.center.x,e.center.y] for e in egos])
velocity=np.diff(xy,axis=0)/np.diff(np.r_[previous.time_us,ts])[:,None]*1e6
ego['velocity'][:]=velocity
types={'vehicle':('VEHICLE',0,'REGULAR_VEHICLE'),'pedestrian':('PEDESTRIAN',1,'PEDESTRIAN'),
       'bicycle':('CYCLIST',2,'BICYCLIST')}
query='''SELECT b.*,cat.name AS category FROM lidar_box b
 JOIN track t ON b.track_record_id=t.record_id JOIN category cat ON t.category_record_id=cat.record_id
 WHERE b.lidar_pc_record_id=?'''
for i,r in enumerate(frames):
    for b in c.execute(query,(r['record_id'],)):
        if b['category'] not in types: continue
        s=track(b['track_record_id'].hex(),*types[b['category']])
        s['position'][i,:2]=np.array([b['x'],b['y']])-center
        s['heading'][i]=b['yaw'];s['velocity'][i]=[b['vx'],b['vy']]
        for k in ['length','width','height']:s[k][i]=b[k]
        s['valid'][i]=1;s['tracking_scores'][i]=1 # GT availability, not detector confidence
# Inclusion depends on observed history, never future-only objects.
tracks={k:v for k,v in tracks.items() if k=='ego' or np.any(
    (v['state']['valid'][:21]>0)&(np.linalg.norm(v['state']['position'][:21,:2],axis=1)<120))}
map_path=args.map or root/'data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg'
if not map_path.is_absolute():map_path=root/map_path
map_path=map_path.resolve()
transform=Transformer.from_crs(epsg,4326,always_xy=True)
corners=[transform.transform(*(center+np.array([x,y]))) for x in [-180,180] for y in [-180,180]]
bbox=(min(p[0] for p in corners),min(p[1] for p in corners),max(p[0] for p in corners),max(p[1] for p in corners))
features={}; nearest=[]
for layer,kind in [('baseline_paths','LANE_SURFACE_STREET'),('crosswalks','CROSSWALK')]:
    table=gpd.read_file(map_path,layer=layer,bbox=bbox).to_crs(epsg=epsg)
    for idx,row in table.iterrows():
        geom=row.geometry
        if geom is None or geom.is_empty or geom.distance(Point(center))>150:continue
        if layer=='baseline_paths':
            if geom.geom_type!='LineString':continue
            nearest.append(geom.distance(Point(center)))
            points=np.asarray(geom.coords)[:,:2]-center
        else:
            if geom.geom_type!='Polygon':continue
            points=np.asarray(geom.exterior.coords)[:,:2]-center
        # Keep complete geometry within selected local map, in meter coordinates.
        feature={'type':kind,'polyline':points.astype(np.float32)}
        if layer=='crosswalks':feature['polygon']=points.astype(np.float32)
        features[f'{layer}_{idx}']=feature
assert nearest and min(nearest)<10, 'Map/ego coordinate mismatch'
for t in tracks.values():
    assert all(np.isfinite(a).all() for a in t['state'].values())
    s=t['state'];assert np.all(s['length'][s['valid']>0]>0)
scenario_id=clip+(f'_gps{args.gps_row}' if anchor_basis=='legacy_sample_gps_row' else f'_t{anchor}')
meta={'id':scenario_id,'scenario_id':scenario_id,'dataset':'nuplan','source_file':clip,
      'coordinate':'waymo','ts':np.arange(81)*.1,'sdc_id':'ego','track_length':81,
      'current_time_index':20,'map_center':np.zeros(3),'metadrive_processed':False,
      'tracks_to_predict':{'ego':{'track_index':0,'track_id':'ego','object_type':'VEHICLE','difficulty':0}}}
scenario={'id':scenario_id,'version':'nuplan_valeo_adapter_v1','length':81,'metadata':meta,
          'tracks':tracks,'map_features':features,'dynamic_map_states':{}}
name=f'sd_nuplan_v1_{scenario_id}.pkl'
dest.mkdir(parents=True,exist_ok=False)
for filename,obj in [(name,scenario),('dataset_summary.pkl',{name:meta}),('dataset_mapping.pkl',{name:''})]:
    with (dest/filename).open('wb') as f:pickle.dump(obj,f)
report={'scenario':name,'tracks':len(tracks),'map_features':len(features),'frames':81,
        'current_timestamp_us':anchor,
        'current_seconds_from_first_gps':(anchor-int(gps[0]['timestamp_us']))/1e6 if anchor_basis=='legacy_sample_gps_row' else None,
        'current_seconds_from_first_lidar':(anchor-all_frames[0]['timestamp'])/1e6,
        'anchor_basis':anchor_basis,'source_db':str(db.relative_to(root)),
        'source_map':str(map_path.relative_to(root)), 'source_clip':clip,
        'dt_max_error_sec':float(np.max(np.abs(np.diff(ts)/1e6-.1))),
        'nearest_lane_center_m':min(nearest),'current_speed_mps':float(np.linalg.norm(velocity[20])),
        'source_epsg':epsg,'origin_xy_m':center.tolist(),'timestamp_us':ts.tolist(),
        'nuplan_devkit_commit':'ce3c323af01c0d7ec5672f7832ef53f9c679aab0',
        'limitations':['Experimental GT nuPlan to AV2-pretrained model transfer.',
          'Vehicle subclasses collapsed to REGULAR_VEHICLE; static obstacles excluded.',
          'Map includes lane/connector centerlines and crosswalks; no lane marking semantics.',
          'Traffic lights omitted: upstream loader asserts on nonempty dynamic map states.',
          'GT availability scores are 1, not learned detector scores.',
          'Language labels not used; annotation frame convention remains provisional.']}
(dest/'conversion.json').write_text(json.dumps(report,indent=2))
c.close()
print(json.dumps({k:v for k,v in report.items() if k!='timestamp_us'},indent=2))
