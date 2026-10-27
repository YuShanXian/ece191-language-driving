"""Recheck fixed candidates under separately named parallel-connector geometry."""
import argparse,json,shutil
from collections import Counter
import numpy as np
from evaluate_candidate_checks import load_graph
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.paths import ROOT,write_json,sha256
from language_selector import action_matches


def checked_relative(value):
    import re
    if not re.fullmatch(r'[a-zA-Z0-9_./-]+',value) or any(p in ('..','') for p in value.split('/')) or value.startswith('/'):
        raise ValueError('Project-relative experiment path required')
    return value


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--frames',type=int,nargs='+')
    parser.add_argument('--manifest',default='project-v2/annotation-sequence-v1/sequence-manifest.json')
    parser.add_argument('--output-tag',default='connector-route-v1');args=parser.parse_args()
    manifest_path=ROOT/'runs'/checked_relative(args.manifest)
    output_root=ROOT/'runs/project-v2'/checked_relative(args.output_tag)
    manifest=json.loads(manifest_path.read_text())
    results=[]
    for entry in manifest:
        if args.frames and entry.get('video_frame') not in args.frames:continue
        source=ROOT/'runs'/checked_relative(entry['run']);output=output_root/checked_relative(entry['key'])
        if (output/'anchored_feasibility.json').exists():raise ValueError('Preserve previous experimental report')
        original=json.loads((source/'anchored_feasibility.json').read_text())
        conversion=json.loads((ROOT/'samples'/entry['sample']/'conversion.json').read_text())
        graph=load_graph(np.asarray(conversion['origin_xy_m']),conversion['source_epsg'],conversion['source_map'])
        expanded,added=add_parallel_connector_edges(graph)
        data=np.load(source/'refined_v2_candidates.npz');center=np.load(source/'internal_0000.npz')['center']
        anchor=original['summary']['past_only_start_node'];rows=original['candidates'];changed=[]
        for row,xy in zip(rows,data['world_xy']):
            points=np.vstack([center[:2],xy]);before=row['route']
            route=expanded.match(points,float(center[6]),start_nodes={anchor}) if anchor else {'matched':False,'failure':'unresolved_observed_start'}
            expanded.settled_lane_changes(route,points,float(center[6]),float(center[3]),float(center[4]))
            row['baseline_route']=before;row['route']=route
            row['rejected_by']=[r for r in row['rejected_by'] if r!='observed_start_road_route']
            if not route['matched']:row['rejected_by'].append('observed_start_road_route')
            row['passes_current_checks']=not row['rejected_by']
            if not before['matched'] and route['matched']:changed.append(row['candidate'])
        matching_by_action={action:[r['candidate'] for r in rows if r['passes_current_checks'] and action_matches(r,action,conversion['current_speed_mps'])] for action in ['lane_change_left','lane_change_right']}
        matching=[r for r in rows if r['candidate'] in matching_by_action['lane_change_right']]
        selected=max(matching,key=lambda r:(r['score'],-r['candidate']))['candidate'] if matching else None
        original['summary'].update(passed_candidates=[r['candidate'] for r in rows if r['passes_current_checks']],
                                   rejection_counts=dict(Counter(x for r in rows for x in r['rejected_by'])))
        original['experimental_route_policy']={'method':'parallel_connector_geometry_v1','added_edges':added,
             'source_report_sha256':sha256(source/'anchored_feasibility.json'),
             'method_sha256':sha256(ROOT/'scripts/mtr_project/connector_routes.py'),
             'runner_sha256':sha256(__file__),'manifest_sha256':sha256(manifest_path),
             'scope':'Exploratory geometry only. Lateral connector motion is permitted by an explicit hypothesis, not verified lane-marking legality. Other screens and past-only start anchor unchanged. No stage completion uses predictions.'}
        output.mkdir(parents=True,exist_ok=True)
        for filename in ['internal_0000.npz','refined_v2_candidates.npz']:shutil.copy2(source/filename,output/filename)
        write_json(output/'anchored_feasibility.json',original)
        result={'key':entry['key'],'video_frame':entry.get('video_frame'),'added_connector_edges':len(added),
                'newly_matched_routes':changed,'matching_right_merge_candidates':[r['candidate'] for r in matching],
                'matching_by_action':matching_by_action,
                'selected_right_merge_candidate':selected,'experiment_run':str(output.relative_to(ROOT/'runs')),
                'baseline_run':entry['run'],'scope':'Geometric connector hypothesis; legal maneuver permission not established.'}
        write_json(output/'comparison.json',result);results.append(result);print(json.dumps(result),flush=True)
    print('Completed comparisons:',len(results))


if __name__=='__main__':main()
