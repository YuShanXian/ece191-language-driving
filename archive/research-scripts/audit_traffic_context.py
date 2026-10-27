"""Attach exact-current signal and explicit map associations without granting permission."""
import argparse
import inspect
import json
import sqlite3
from collections import Counter,defaultdict
from functools import lru_cache
from nuplan.common.maps.maps_datatypes import LaneConnectorType,StopLineType
from nuplan.common.maps.nuplan_map.lane_connector import NuPlanLaneConnector
from mtr_project.traffic_context import map_ids,signal_observations,describe_route
from mtr_project.paths import ROOT,sha256,write_json


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def enum_label(enum,value):
    try:return enum(value).name
    except (ValueError,TypeError):return 'UNRECOGNIZED'


def connector_map(map_path):
    with sqlite3.connect(map_path.as_uri()+'?mode=ro',uri=True) as connection:
        connection.row_factory=sqlite3.Row
        stops={};by_lane=defaultdict(list);by_connector=defaultdict(list)
        for row in connection.execute('SELECT fid,stop_polygon_type_fid,lane_fids,lane_connector_fids FROM stop_polygons ORDER BY fid'):
            identifier=str(row['fid'])
            stops[identifier]={'id':identifier,'raw_type':row['stop_polygon_type_fid'],'sdk_enum':enum_label(StopLineType,row['stop_polygon_type_fid'])}
            for lane in map_ids(row['lane_fids']):by_lane[lane].append(identifier)
            for connector in map_ids(row['lane_connector_fids']):by_connector[connector].append(identifier)
        result={}
        for row in connection.execute('SELECT fid,exit_lane_fid,entry_lane_fid,turn_type_fid,traffic_light_stop_line_fids FROM lane_connectors ORDER BY fid'):
            identifier=str(row['fid']);upstream=str(row['exit_lane_fid']);relations=defaultdict(list)
            for stop in map_ids(row['traffic_light_stop_line_fids']):relations[stop].append('connector_traffic_light_stop_line_fids')
            for stop in by_connector[identifier]:relations[stop].append('stop_polygon_lane_connector_fids')
            for stop in by_lane[upstream]:relations[stop].append('stop_polygon_upstream_lane_fids')
            result[identifier]={'connector_id':identifier,'upstream_lane_id':upstream,'downstream_lane_id':str(row['entry_lane_fid']),
                'raw_turn_type':row['turn_type_fid'],'turn_type_sdk_enum':enum_label(LaneConnectorType,row['turn_type_fid']),
                'raw_stop_region_associations':[{'id':stop,'relations':kinds,'region':stops.get(stop)} for stop,kinds in sorted(relations.items())],
                'association_scope':'Raw map references only; no geometric disambiguation, stop-line crossing test, stop requirement inference or legal permission.'}
    return result


def counts(rows):
    complete=[r for r in rows if r['context']['status']=='described']
    entries=[r for r in complete if r['context']['has_predicted_connector_entry']]
    unresolved={'unobserved','unknown','ambiguous'}
    return {'candidates':len(rows),'matched_routes':len(complete),'predicted_connector_entry_candidates':len(entries),
        'current_red_on_predicted_route':sum('red' in r['context']['future_entry_signal_classes'] for r in entries),
        'current_yellow_on_predicted_route':sum('yellow' in r['context']['future_entry_signal_classes'] for r in entries),
        'unresolved_signal_on_predicted_route':sum(bool(unresolved.intersection(r['context']['future_entry_signal_classes'])) for r in entries),
        'all_entries_currently_green':sum(r['context']['all_future_entries_currently_green'] for r in entries),
        'no_predicted_connector_entry_matched':len(complete)-len(entries)}


def build(spec_path):
    spec=json.loads(spec_path.read_text());parent_path=ROOT/spec['source_evaluation'];parent=json.loads(parent_path.read_text())
    verified_path=parent_path.with_name('verification.json');verified=json.loads(verified_path.read_text())
    if verified['evaluation_sha256']!=digest(parent_path):raise ValueError('Parent evaluation no longer verified')
    sources={str(p.relative_to(ROOT)):digest(p) for p in [spec_path,parent_path,verified_path]}
    for mapping in [parent['source_sha256'],parent['implementation_sha256']]:
        for name,expected in mapping.items():
            if digest(ROOT/name)!=expected:raise ValueError('Parent source changed: '+name)
    windows=[];map_cache={}
    for item in parent['windows']:
        window=item['window'];screen_path=ROOT/'runs'/window['run']/'anchored_feasibility.json';screen=json.loads(screen_path.read_text())
        conversion_path=ROOT/'samples'/window['sample']/'conversion.json';conv=json.loads(conversion_path.read_text());db=ROOT/conv['source_db'];map_path=ROOT/conv['source_map']
        for path in [screen_path,conversion_path,db,map_path]:sources[str(path.relative_to(ROOT))]=digest(path)
        if str(map_path) not in map_cache:map_cache[str(map_path)]=connector_map(map_path)
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as connection:
            current=connection.execute('SELECT t.lane_connector_id,t.status FROM traffic_light_status t JOIN lidar_pc p ON p.record_id=t.lidar_pc_record_id WHERE p.timestamp=? ORDER BY t.lane_connector_id,t.status',(window['timestamp_us'],)).fetchall()
            anchors=connection.execute('SELECT COUNT(*) FROM lidar_pc WHERE timestamp=?',(window['timestamp_us'],)).fetchone()[0]
            if anchors!=1:raise ValueError('Current timestamp is missing or ambiguous')
        observations=signal_observations(current);rows=[]
        if len(screen['candidates'])!=64:raise ValueError('Incomplete candidate population')
        for row in screen['candidates']:
            context=describe_route(row.get('route') or {},observations,map_cache[str(map_path)])
            rows.append({'candidate':row['candidate'],'passes_baseline_checks':row['passes_current_checks'],
                'selected_by_actions':[choice['action'] for choice in item['choices'] if choice['all64']['candidate']==row['candidate']],
                'context':context})
        if [r['candidate'] for r in rows]!=list(range(1,65)):raise ValueError('Candidate IDs missing or duplicated')
        passing=[r for r in rows if r['passes_baseline_checks']]
        windows.append({'window':window,'exact_current_signal_rows':[list(r) for r in current],'current_signal_connector_count':len(observations),
            'current_signal_status_counts':dict(Counter(status for _,status in current)),
            'all_candidate_counts':counts(rows),'passing_candidate_counts':counts(passing),'candidates':rows})
    if len(windows)!=13 or sum(w['passing_candidate_counts']['candidates'] for w in windows)!=62:raise ValueError('Challenge population changed')
    all_rows=[r for w in windows for r in w['candidates']];passing=[r for r in all_rows if r['passes_baseline_checks']]
    code=['scripts/audit_traffic_context.py','scripts/mtr_project/traffic_context.py']
    return {'specification':spec,'windows':windows,'all_candidate_counts':counts(all_rows),'passing_candidate_counts':counts(passing),
        'source_sha256':sources,'implementation_sha256':{name:digest(ROOT/name) for name in code},
        'sdk_source_sha256':{inspect.getfile(item):digest(inspect.getfile(item)) for item in [LaneConnectorType,NuPlanLaneConnector]},
        'selection_changed':False,'future_signals_queried':False,'scope':spec['scope']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    spec_path=ROOT/'config/traffic-context-v1.json';spec=json.loads(spec_path.read_text());folder=ROOT/'runs/project-v2'/spec['output_tag'];path=folder/'audit.json'
    if not args.verify and folder.exists():raise FileExistsError('Preserve prior traffic context audit')
    if not args.verify:
        folder.mkdir();write_json(folder/'specification.json',spec)
    result=build(spec_path)
    if args.verify:
        saved=json.loads(path.read_text())
        if saved!=result:raise ValueError('Rebuilt exact-current traffic audit differs')
        verification={'status':'passed_rebuilt_traffic_context','audit_sha256':sha256(path),'verifier_sha256':sha256(__file__),
            'windows':len(result['windows']),'candidates':result['all_candidate_counts']['candidates'],
            'scope':'Reopened exact-current DB queries, map references and frozen candidate nodes; reconstructed the complete audit using the same tested extraction method. No future-signal or legal-compliance validation.'}
        write_json(folder/'verification.json',verification)
    else:write_json(path,result)
    print(json.dumps({'mode':'verify' if args.verify else 'create','all':result['all_candidate_counts'],'passing':result['passing_candidate_counts'],
        'windows_with_current_signals':sum(bool(w['exact_current_signal_rows']) for w in result['windows'])},indent=2))


if __name__=='__main__':main()
