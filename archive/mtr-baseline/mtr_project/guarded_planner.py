"""Opt-in complete-pool geometry experiment around the frozen language planner."""
from copy import deepcopy
from .corridor_reserve import choose_guarded


def apply_pool_guard(original,candidates,pool,margin,speed):
    if type(margin) not in (int,float) or margin not in (0.,.05,.1,.2):raise ValueError('Use a declared 0/5/10/20cm reserve')
    result=deepcopy(original)
    result['original_choice']={'candidate':original.get('candidate'),'status':original['status']}
    result['geometry_filter']={'enabled':True,'target_reserve_m':margin,'scope':'Extra geometry experiment only; no verified control or execution.'}
    if result.get('stage',{}).get('state')!='active':return result
    result['candidate']=None;result['matching_candidates']=[]
    action=result['stage']['action']
    if action not in ('lane_change_left','lane_change_right'):
        result['status']='unsupported_geometry_action';return result
    if pool is None:
        result['status']='missing_geometry_audit';return result
    if margin not in pool['margins_m']:raise ValueError('Margin not included in the saved audit')
    audits={r['candidate']:r for r in pool['audited_candidates']}
    if len(audits)!=len(pool['audited_candidates']):raise ValueError('Duplicate audit candidate')
    checked=choose_guarded(candidates,audits,action,speed,margin)
    result.update(checked)
    return result
