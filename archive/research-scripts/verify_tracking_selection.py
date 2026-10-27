"""Reopen the declared population and independently reconstruct the retained-ID ranking."""
import json
from functools import lru_cache
from mtr_project.paths import ROOT,sha256,write_json
from language_selector import action_matches


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def main():
    path=ROOT/'runs/project-v2/tracking-selection-v1/evaluation.json';saved=json.loads(path.read_text())
    for group in ['source_sha256','implementation_sha256']:
        for name,expected in saved[group].items():
            if digest(ROOT/name)!=expected:raise ValueError('Changed selection dependency: '+name)
    parent=json.loads((ROOT/saved['specification']['source_proposals']).read_text())
    tracking=json.loads((ROOT/saved['specification']['source_tracking']).read_text())
    required={(dt,angle) for dt in (.1,.05) for angle in (-3.,0.,3.)}
    indexed={(r['window'],r['action']):r for r in saved['results']}
    if len(indexed)!=len(saved['results']):raise ValueError('Duplicate action/window pair')
    expected_keys=set();skipped=[];original_count=filtered_count=replaced=removed=0
    for window in parent['windows']:
        if not window['selections']:
            skipped.append(window['key'])
            if window['source_task']['stage']['state']!='completed':raise ValueError('Unexpected skipped task state')
            continue
        folder=ROOT/'runs'/window['run'];screen=json.loads((folder/'anchored_feasibility.json').read_text())
        speed=json.loads((ROOT/'samples'/screen['summary']['sample']/'conversion.json').read_text())['current_speed_mps']
        for action,choice in window['selections'].items():
            key=(window['key'],action);expected_keys.add(key);result=indexed[key];filtered=result['filtered']
            stage=window['source_task']['stage'] if window['source_task'] else {'state':'active','action':action}
            if result['original']['stage']!=stage or filtered['stage']!=stage:raise ValueError('Task state was changed')
            eligible=[r for r in screen['candidates'] if r['passes_current_checks'] and action_matches(r,action,speed)]
            original=max(eligible,key=lambda r:(r['score'],-r['candidate']),default=None)
            original_id=original['candidate'] if original else None
            if original_id!=choice['candidate'] or original_id!=result['original']['candidate']:raise ValueError('Historical choice mismatch')
            retained=[]
            for candidate in eligible:
                rows=[r for r in tracking['results'] if r['window']==window['key'] and r['candidate']==candidate['candidate']]
                if len(rows)!=6 or {(r['simulation_dt'],r['initial_tire_angle_deg']) for r in rows}!=required:raise ValueError('Incomplete tracking grid')
                passed=all(r['action']==action and r['final_half_second_target_reserve'] is True
                           and r['simulated_pose_checks']['body_passed'] is True
                           and r['simulated_pose_checks']['cv_collision_passed'] is True
                           and r['metrics']['reverse_speed_samples']==0
                           and r['metrics']['model_steering_clamp_samples']==0 for r in rows)
                if filtered['tracking_candidate_checks'][str(candidate['candidate'])]['passed']!=passed:raise ValueError('Candidate decision mismatch')
                if passed:retained.append(candidate)
            chosen=max(retained,key=lambda r:(r['score'],-r['candidate']),default=None)
            chosen_id=chosen['candidate'] if chosen else None
            if filtered['candidate']!=chosen_id or filtered['matching_candidates']!=[r['candidate'] for r in retained]:raise ValueError('Filtered ranking mismatch')
            status='selected_under_tracking_checks' if retained else 'no_matching_candidate'
            if filtered['status']!=status:raise ValueError('Filtered status mismatch')
            original_count+=original_id is not None;filtered_count+=chosen_id is not None
            replaced+=chosen_id is not None and chosen_id!=original_id
            removed+=original_id is not None and chosen_id is None
    if set(indexed)!=expected_keys or [r['window'] for r in saved['skipped']]!=skipped:raise ValueError('Population changed')
    counts={'active_action_window_pairs':len(indexed),'original_proposals':original_count,'filtered_proposals':filtered_count,
            'replaced':replaced,'removed':removed,'completed_windows_skipped':len(skipped)}
    if saved['counts']!=counts:raise ValueError('Summary counts do not match full population')
    receipt={'status':'passed_declared_selection_checks','evaluation_sha256':digest(path),'counts':counts,
             'verification_method':'Independent retained-ID and score ranking reconstruction from hashed candidate screens and six-case tracking records; underlying geometric predicates are shared.',
             'verifier_sha256':sha256(__file__)}
    write_json(path.with_name('verification.json'),receipt);print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
