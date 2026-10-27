"""Evaluation-only attribution of missing turn candidates; never used by planning."""
from collections import Counter
import numpy as np
from language_selector import action_matches
from trajectory_checks import angle_diff, headings

BUCKETS = ('route_unresolved', 'no_requested_turn_on_matched_route',
           'turn_with_incompatible_other_actions', 'matching_but_rejected', 'matching_and_passed')


def attribute_candidates(rows, action, speed):
    if action not in ('turn_left', 'turn_right'):
        raise ValueError('Turn diagnostic only')
    identifiers = [r['candidate'] for r in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Duplicate candidates')
    members = {key: [] for key in BUCKETS}
    rejection_counts = Counter()
    rejection_combinations = Counter()
    for row in rows:
        if row['passes_current_checks'] != (not row['rejected_by']):
            raise ValueError('Inconsistent saved screening result')
        route = row['route']
        if not route.get('matched'):
            bucket = 'route_unresolved'
        elif not any(t['action'] == action for t in route.get('turns', [])):
            bucket = 'no_requested_turn_on_matched_route'
        elif not action_matches(row, action, speed):
            bucket = 'turn_with_incompatible_other_actions'
        elif row['rejected_by']:
            bucket = 'matching_but_rejected'
            reasons = sorted(set(row['rejected_by']))
            rejection_counts.update(reasons)
            rejection_combinations[' + '.join(reasons)] += 1
        else:
            bucket = 'matching_and_passed'
        members[bucket].append(row['candidate'])
    return {'counts': {key: len(value) for key, value in members.items()},
            'candidate_ids': members,
            'matching_rejections_overlapping': dict(rejection_counts),
            'matching_rejection_combinations_exclusive': dict(rejection_combinations)}


def curve_heading_change(points, initial_heading):
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or not np.isfinite(points).all():
        raise ValueError('Expected finite Nx2 trajectory')
    return float(np.degrees(angle_diff(headings(points, initial_heading)[-1], initial_heading)))


def curve_bucket(degrees):
    # Shape-only endpoint heading proxy; never a semantic or legal maneuver label.
    if not np.isfinite(degrees):
        raise ValueError('Nonfinite heading change')
    return 'left_bend' if degrees >= 30 else 'right_bend' if degrees <= -30 else 'under_30_degrees'
