"""Opt-in cached tracking filter; never bypass language state or missing evidence."""
from copy import deepcopy
import math
from language_selector import action_matches

REQUIRED_CASES=frozenset((dt,angle) for dt in [.1,.05] for angle in [-3.,0.,3.])


def candidate_evidence(rows,action):
    keys=[(r['simulation_dt'],r['initial_tire_angle_deg']) for r in rows]
    if len(keys)!=6 or set(keys)!=REQUIRED_CASES:raise ValueError('Missing, duplicate or unexpected tracking settings')
    if any(r['action']!=action for r in rows):raise ValueError('Tracking evidence for a different action')
    reasons=[]
    for r in rows:
        geometry=r['simulated_pose_checks'];metrics=r['metrics'];case=f'dt={r["simulation_dt"]:.2f},angle={r["initial_tire_angle_deg"]:+.0f}'
        for key,value in [('road',geometry['body_passed']),('cv_overlap',geometry['cv_collision_passed']),('target_reserve',r['final_half_second_target_reserve'])]:
            if type(value) is not bool:raise ValueError('Tracking flags must be explicit booleans')
            if not value:reasons.append({'case':case,'reason':key})
        for key in ['reverse_speed_samples','model_steering_clamp_samples']:
            value=metrics[key]
            if type(value) is not int or value<0:raise ValueError('Tracking event counts must be nonnegative integers')
            if value:reasons.append({'case':case,'reason':key})
    return {'passed':not reasons,'reasons':reasons,'cases':6}


def apply_tracking_filter(original,candidates,tracking,speed):
    result=deepcopy(original)
    result['original_choice']={'candidate':original.get('candidate'),'status':original['status']}
    result['tracking_filter']={'enabled':True,'required_cases':6,'scope':'Cached single-merge feedback experiment; not a real-vehicle safety certificate.'}
    if result.get('stage',{}).get('state')!='active':return result
    result['candidate']=None;result['matching_candidates']=[]
    action=result['stage']['action']
    if action not in ('lane_change_left','lane_change_right'):
        result['status']='unsupported_tracking_action';return result
    if len({r['candidate'] for r in candidates})!=len(candidates):raise ValueError('Duplicate candidate IDs')
    if any(not math.isfinite(r['score']) or r['score']<0 for r in candidates):raise ValueError('Invalid model score')
    eligible=[r for r in candidates if r.get('passes_current_checks') is True and action_matches(r,action,speed)]
    if not eligible:
        result['status']='no_matching_candidate';return result
    if tracking is None:
        result['status']='missing_tracking_audit';return result
    audit=tracking['by_candidate'];checks={};retained=[]
    for row in eligible:
        evidence=audit.get(str(row['candidate']))
        if evidence is None:
            result['status']='missing_tracking_audit';result['missing_candidate']=row['candidate'];return result
        check=candidate_evidence(evidence['rollouts'],action);checks[str(row['candidate'])]=check
        if check['passed']:retained.append(row)
    chosen=max(retained,key=lambda r:(r['score'],-r['candidate']),default=None)
    result.update(status='selected_under_tracking_checks' if chosen else 'no_matching_candidate',candidate=chosen['candidate'] if chosen else None,
                  matching_candidates=[r['candidate'] for r in retained],tracking_candidate_checks=checks)
    return result
