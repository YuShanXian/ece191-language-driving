"""Local lane correspondence, independent of downstream route length."""

import math
import numpy as np
from .geometry import tangent, angle_diff


def connection_geometry(source, target):
    a = np.asarray(source.baseline.coords[-1])[:2]
    b = np.asarray(target.baseline.coords[0])[:2]
    h0 = tangent(source.baseline, a)
    h1 = tangent(target.baseline, b)
    turn = angle_diff(h1, h0)
    mid = h0 + turn / 2
    # Remove lateral displacement explained by a gently curving road.
    lateral = float((b - a) @ np.array([-math.sin(mid), math.cos(mid)]))
    return turn, lateral


def lane_rank_error(source, target, groups):
    turn, _ = connection_geometry(source, target)
    si = source.lane_index or 1
    ti = target.lane_index or 1
    if turn < math.radians(-30):
        si = max(n.lane_index or 1 for n in groups[source.lane_group]) - si
        ti = max(n.lane_index or 1 for n in groups[target.lane_group]) - ti
        si = min(si, len(groups[target.lane_group]) - 1)
    else:
        si = min(si, max(n.lane_index or 1 for n in groups[target.lane_group]))
    return abs(si - ti)


def straight_rank_error(source, target, groups, nodes, edges):
    """Infer lane renumbering from the neighboring native straight links.

    Turn-only lanes disappear at a junction: incoming lane 3 can become exit
    lane 1. Comparing their raw indices sends an unmarked straight route into
    the wrong exit lane. Use the nearest aligned native lane correspondence.
    """
    anchors = []
    for lane in groups[source.lane_group]:
        matches = []
        for connector, rel in edges.get(lane.key, {}).items():
            if rel != 'forward' or not connector.startswith('C'):
                continue
            for key, r in edges.get(connector, {}).items():
                end = nodes[key]
                if r != 'forward' or end.lane_group != target.lane_group:
                    continue
                turn, lateral = connection_geometry(lane, end)
                if abs(turn) < math.radians(30):
                    matches.append((abs(lateral), (end.lane_index or 1) - (lane.lane_index or 1)))
        if matches:
            anchors.append(min(matches))
    if not anchors:
        return lane_rank_error(source, target, groups)
    offset = sorted(anchors)[0][1]
    expected = max(1, min(max(n.lane_index or 1 for n in groups[target.lane_group]),
                          (source.lane_index or 1) + offset))
    return abs(expected - (target.lane_index or 1))

