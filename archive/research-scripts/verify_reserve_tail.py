"""Reopen stored proposal artifacts and re-evaluate every accepted merge path."""
import json
import numpy as np
from evaluate_candidate_checks import load_graph,current_obstacles
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.reserve_proposal import evaluate_proposal
from mtr_project.paths import ROOT,sha256,write_json


def main():
    base=ROOT/'runs/project-v2/reserve-tail-v1';source=base/'experiment.json';experiment=json.loads(source.read_text())
    if experiment['status']!='completed' or len(experiment['windows'])!=23:raise ValueError('Incomplete experiment')
    for mapping in ['source_sha256','implementation_sha256']:
        for name,expected in experiment[mapping].items():
            if sha256(ROOT/name)!=expected:raise ValueError('Experiment source changed: '+name)
    verified=[];sources={str(source.relative_to(ROOT)):sha256(source)}
    for window in experiment['windows']:
        folder=ROOT/'runs'/window['run'];prior=ROOT/'runs'/window['source_run']
        for name,expected in window['output_sha256'].items():
            path=folder/name
            if sha256(path)!=expected:raise ValueError('Saved output changed: '+str(path))
            sources[str(path.relative_to(ROOT))]=expected
        if sha256(folder/'internal_0000.npz')!=sha256(prior/'internal_0000.npz'):raise ValueError('Raw model output changed')
        raw=np.load(folder/'internal_0000.npz');center=raw['center'];derived=np.load(folder/'refined_v2_candidates.npz');original=np.load(prior/'refined_v2_candidates.npz')['world_xy']
        if not np.array_equal(derived['scores'],raw['scores']):raise ValueError('Scores changed')
        if not np.array_equal(original[:,:30],derived['world_xy'][:,:30]):raise ValueError('First3s changed')
        report=json.loads((folder/'anchored_feasibility.json').read_text());accepted={r['candidate']:r for r in window['accepted']}
        if set(accepted)!={r['candidate'] for r in report['candidates'] if r['passes_current_checks']}:raise ValueError('Accepted flags differ')
        for i in range(64):
            if i+1 not in accepted and not np.array_equal(original[i],derived['world_xy'][i]):raise ValueError('Unaccepted path changed')
        if not accepted:continue
        print('RECHECK RESERVE',window['key'],flush=True)
        conv=json.loads((ROOT/'samples'/report['summary']['sample']/'conversion.json').read_text())
        graph,_=add_parallel_connector_edges(load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']))
        obstacles,bad=current_obstacles(conv)
        if bad:raise ValueError('Invalid current obstacles')
        for candidate,entry in accepted.items():
            points=np.vstack([center[:2],derived['world_xy'][candidate-1]]).astype(float)
            result=evaluate_proposal(points,raw['world_xy'][candidate-1],center,np.asarray(report['summary']['initial_acceleration_from_past_only']),graph,report['summary']['past_only_start_node'],obstacles,entry['action'],conv['current_speed_mps'],experiment['geometry'],experiment['specification']['target_reserve_m'],full=True)
            if not result['passed'] or result['skipped_checks']:raise ValueError('Reopened accepted path failed checks')
            if result!=report['candidates'][candidate-1]['reserve_check']:raise ValueError('Recomputed check differs from recorded accepted check')
            verified.append({'run':window['run'],**entry,'peak_front_tire_angle_deg':result['details']['inverse_motion_diagnostic']['peak_abs_front_tire_angle_deg'],
                'low_or_reverse_speed_segments':result['details']['inverse_motion_diagnostic']['low_or_reverse_speed_segments']})
    receipt={'experiment_sha256':sha256(source),'source_sha256':sources,'validator_sha256':sha256(__file__),'windows':23,'accepted_paths_rechecked':len(verified),
        'raw_outputs_unchanged':True,'scores_unchanged':True,'first_three_seconds_unchanged':True,'unaccepted_arrays_unchanged':True,'verified':verified,
        'scope':'Recomputed declared geometry/motion checks on saved artifacts. Same checker implementation, not independent physical ground truth or a controller validation.'}
    write_json(base/'verification.json',receipt);print(json.dumps({'accepted_paths_rechecked':len(verified),'verified':verified},indent=2))


if __name__=='__main__':main()
