"""Additional target-corridor reserve under two explicit heading hypotheses."""
import math
import numpy as np
from trajectory_checks import footprint
from language_selector import action_matches


def margin_key(margin):return f'{margin:.2f}'


def target_reserve(points,heading_sets,length,width,target,event_time,margins,dt=.05):
    points=np.asarray(points,float);angles=[np.asarray(h,float) for h in heading_sets]
    if points.ndim!=2 or points.shape[1]!=2 or len(points)<2 or not np.isfinite(points).all():raise ValueError('Finite center points required')
    if not angles or any(a.shape!=(len(points),) or not np.isfinite(a).all() for a in angles):raise ValueError('Matching finite headings required')
    if not all(math.isfinite(v) and v>0 for v in [length,width,dt]) or not math.isfinite(event_time) or event_time<0:raise ValueError('Invalid geometry or times')
    if not margins or any(not math.isfinite(m) or m<0 for m in margins) or len({margin_key(m) for m in margins})!=len(margins):raise ValueError('Distinct nonnegative margins required')
    horizon=(len(points)-1)*dt;start=horizon-.5
    if start<0 or event_time>start+1e-9:return {margin_key(m):False for m in margins}
    indices=np.flatnonzero(np.arange(len(points))*dt>=start-1e-9)
    bodies=[footprint(points[i],a[i],length,width) for a in angles for i in indices]
    regions={m:target.buffer(-m) if m else target for m in margins}
    return {margin_key(m):all(regions[m].covers(body) for body in bodies) for m in margins}


def choose_guarded(candidates,audits,action,speed,margin):
    if action not in ('lane_change_left','lane_change_right'):raise ValueError('This experiment evaluates single merges only')
    if not math.isfinite(margin) or margin<0:raise ValueError('Invalid reserve')
    passing=[r for r in candidates if r['passes_current_checks']]
    if len({r['candidate'] for r in candidates})!=len(candidates):raise ValueError('Duplicate candidates')
    for row in passing:
        if row['candidate'] not in audits:raise ValueError('Cannot silently accept an unaudited passing candidate')
    eligible=[]
    for row in passing:
        if not action_matches(row,action,speed):continue
        check=audits[row['candidate']]
        if check['joint_geometry_passed'] and check['merge_target_reserve'][margin_key(margin)]:eligible.append(row)
    chosen=max(eligible,key=lambda r:(r['score'],-r['candidate']),default=None)
    return {'candidate':chosen['candidate'] if chosen else None,'matching_candidates':[r['candidate'] for r in eligible],
        'status':'selected_under_extra_geometry_checks' if chosen else 'no_matching_candidate',
        'scope':'Single-merge offline geometry experiment; no verified controller or execution.'}
