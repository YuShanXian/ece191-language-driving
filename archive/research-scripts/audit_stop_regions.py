"""Read-only fixed-population stop-region geometry and official map-association audit."""
import argparse,inspect,json
from pathlib import Path
from functools import lru_cache
import numpy as np
import geopandas as gpd
from shapely.affinity import translate
from shapely.geometry import Point
from nuplan.common.maps.nuplan_map.lane_connector import NuPlanLaneConnector
from nuplan.common.maps.nuplan_map.stop_line import NuPlanStopLine
from nuplan.common.maps.nuplan_map.utils import get_row_with_value
from trajectory_checks import headings
from mtr_project.pose_geometry import interpolate_centers_and_angles
from mtr_project.stop_region_geometry import sampled_contacts
from mtr_project.paths import ROOT,sha256,write_json


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def layers(path,epsg):
    result={}
    for key in ['stop_polygons','baseline_paths','lane_connectors']:
        frame=gpd.read_file(path,layer=key,fid_as_index=True).to_crs(epsg=epsg)
        frame.index=frame.index.astype(str);frame['fid']=frame.index
        # Match GPKGMapsDB: string index/fid, original numeric reference columns including NaN.
        result[key]=frame
    return result


def build(spec_path):
    spec=json.loads(spec_path.read_text());parent_path=ROOT/spec['source_audit'];parent=json.loads(parent_path.read_text())
    receipt_path=parent_path.with_name('verification.json');receipt=json.loads(receipt_path.read_text())
    if receipt['audit_sha256']!=digest(parent_path) or receipt['verifier_sha256']!=digest(ROOT/'scripts/audit_traffic_context.py'):
        raise ValueError('Unverified traffic audit')
    sources={str(p.relative_to(ROOT)):digest(p) for p in [spec_path,parent_path,receipt_path]}
    for mapping in [parent['source_sha256'],parent['implementation_sha256'],parent['sdk_source_sha256']]:
        for name,expected in mapping.items():
            if digest(ROOT/name)!=expected:raise ValueError('Upstream source changed: '+name)
    challenge_path=ROOT/parent['specification']['source_evaluation'];challenge=json.loads(challenge_path.read_text())
    for name,expected in challenge['source_sha256'].items():
        if digest(ROOT/name)!=expected:raise ValueError('Original challenge input changed: '+name)
    windows=[];cache={};sdk_checks={}
    for w in parent['windows']:
        window=w['window'];conv_path=ROOT/'samples'/window['sample']/'conversion.json';conv=json.loads(conv_path.read_text())
        if conv['current_timestamp_us']!=window['timestamp_us']:raise ValueError('Current anchor differs')
        run=ROOT/'runs'/window['run'];raw_path=run/'internal_0000.npz';refined_path=run/'refined_v2_candidates.npz'
        # anchored screen uses the same fixed bounded-refined array recorded by the challenge.
        for p in [conv_path,raw_path,refined_path]:sources[str(p.relative_to(ROOT))]=digest(p)
        raw=np.load(raw_path);refined=np.load(refined_path);center=raw['center'];origin=np.asarray(conv['origin_xy_m'])
        map_path=ROOT/conv['source_map'];cachekey=(str(map_path),conv['source_epsg'])
        if cachekey not in cache:cache[cachekey]=layers(map_path,conv['source_epsg'])
        data=cache[cachekey];rows=[]
        for c in w['candidates']:
            if not c['passes_baseline_checks']:continue
            points=np.vstack((center[:2],refined['world_xy'][c['candidate']-1]));angles=headings(points,float(center[6]))
            dense,dense_angles=interpolate_centers_and_angles(points,angles);visits=[]
            for visit in c['context']['connector_visits']:
                identifier=visit['connector_id'];context=visit['map_context'];associations=[]
                if context is None:
                    visits.append(dict(connector_id=identifier,status='missing_connector_map',context=visit));continue
                sdkkey=cachekey+(identifier,)
                if sdkkey not in sdk_checks:
                    connector=NuPlanLaneConnector(identifier,None,data['lane_connectors'],data['baseline_paths'],None,data['stop_polygons'],None,None)
                    # SDK casts the full nullable reference column to int for matching;
                    # preserve original NaNs and silence only its invalid-cast warning.
                    with np.errstate(invalid='ignore'):
                        official=[s.id for s in connector.stop_lines]
                        baseline=connector.baseline_path.linestring
                    sdk_checks[sdkkey]=(official,baseline)
                official,baseline=sdk_checks[sdkkey]
                for association in context['raw_stop_region_associations']:
                    sid=association['id'];record=dict(**association,official_traffic_light_stop_selection=sid in official)
                    if sid not in data['stop_polygons'].index:record['geometry_status']='missing'
                    else:
                        polygon=data['stop_polygons'].loc[sid].geometry
                        record.update(geometry_status='measured',baseline_intersects_region=bool(baseline.intersects(polygon)),
                            baseline_start_distance_m=float(Point(baseline.coords[0]).distance(polygon)),
                            sampled_contacts=sampled_contacts(dense,dense_angles,float(center[3]),float(center[4]),translate(polygon,-origin[0],-origin[1]),spec['sampling_dt_seconds']))
                    associations.append(record)
                visits.append(dict(connector_id=identifier,status='measured',visit_kind=visit['kind'],
                    center_node_transition_interval_s=visit['center_node_transition_interval_s'],current_signal=visit['current_signal'],
                    official_traffic_light_stop_ids=official,raw_associations=associations))
            rows.append(dict(candidate=c['candidate'],selected_by_actions=c['selected_by_actions'],connector_visits=visits,
                path_source=str(refined_path.relative_to(ROOT)),pose_model='frozen central tangent with interpolated midpoints'))
        windows.append(dict(window=window,candidates=rows))
    if len(windows)!=13 or sum(len(w['candidates']) for w in windows)!=62:raise ValueError('Fixed population changed')
    associations=[a for w in windows for c in w['candidates'] for v in c['connector_visits'] for a in v.get('raw_associations',[])]
    stats=dict(windows=len(windows),candidates=62,association_occurrences=len(associations),
        missing_geometries=sum(a['geometry_status']=='missing' for a in associations),
        official_traffic_stop_occurrences=sum(a['official_traffic_light_stop_selection'] for a in associations),
        center_contact_occurrences=sum(a.get('sampled_contacts',{}).get('center',{}).get('sample_count',0)>0 for a in associations),
        front_edge_contact_occurrences=sum(a.get('sampled_contacts',{}).get('front_edge',{}).get('sample_count',0)>0 for a in associations),
        body_contact_occurrences=sum(a.get('sampled_contacts',{}).get('body',{}).get('sample_count',0)>0 for a in associations))
    code=['scripts/audit_stop_regions.py','scripts/mtr_project/stop_region_geometry.py','scripts/trajectory_checks.py','scripts/mtr_project/pose_geometry.py']
    sdk_sources={inspect.getfile(item):digest(inspect.getfile(item)) for item in [NuPlanLaneConnector,NuPlanStopLine,get_row_with_value]}
    loader=Path(inspect.getfile(NuPlanLaneConnector)).parents[3]/'database/maps_db/gpkg_mapsdb.py'
    sdk_sources[str(loader)]=digest(loader)
    return dict(specification=spec,windows=windows,counts=stats,source_sha256=sources,
        implementation_sha256={name:digest(ROOT/name) for name in code},
        sdk_source_sha256=sdk_sources,
        selection_changed=False,future_signals_queried=False,scope=spec['scope'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');args=p.parse_args()
    spec_path=ROOT/'config/stop-region-geometry-v1.json';spec=json.loads(spec_path.read_text());folder=ROOT/'runs/project-v2'/spec['output_tag'];path=folder/'audit.json'
    if not args.verify:
        if folder.exists():raise FileExistsError('Preserve existing stop-region experiment')
        folder.mkdir();write_json(folder/'specification.json',spec)
    result=build(spec_path)
    if args.verify:
        if result!=json.loads(path.read_text()):raise ValueError('Stop-region rebuild differs')
        write_json(folder/'verification.json',dict(status='passed_rebuilt_stop_region_audit',audit_sha256=sha256(path),
            verifier_sha256=sha256(__file__),counts=result['counts'],scope='Reopened all original map and candidate inputs, called installed SDK association method, reconstructed sampled contacts; same extraction method, not legal or physical ground truth.'))
    else:write_json(path,result)
    print(json.dumps(result['counts'],indent=2))


if __name__=='__main__':main()
