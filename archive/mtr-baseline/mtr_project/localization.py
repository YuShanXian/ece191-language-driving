"""Causal map localization from the current measured pose and past node only."""
import math
from shapely.geometry import Point
from trajectory_checks import angle_diff, tangent, footprint


def locate_pose(graph, xy, heading, length, width, previous_node=None, ambiguity_margin=.35):
    point = Point(xy)
    choices = []
    for idx in graph.tree.query(point, predicate='intersects'):
        key = graph.keys[int(idx)]
        node = graph.nodes[key]
        difference = abs(angle_diff(heading, tangent(node.baseline, xy)))
        if difference <= math.radians(60):
            choices.append((node.baseline.distance(point), key))
    choices.sort()
    if not choices:
        return {'node': None, 'reason': 'outside_road_or_wrong_direction', 'body_inside_node': False}
    keys = {key for _, key in choices}
    # Hysteresis uses only a previously observed node. Never use a future route.
    if previous_node in keys:
        selected = previous_node
    else:
        reachable = [(d, key) for d, key in choices if previous_node is None or
                     key in graph.edges.get(previous_node, {})]
        if not reachable:
            return {'node': None, 'reason': 'unobserved_transition', 'body_inside_node': False}
        if len(reachable)>1 and reachable[1][0]-reachable[0][0] < ambiguity_margin:
            return {'node': None, 'reason': 'ambiguous_overlap', 'body_inside_node': False}
        selected = reachable[0][1]
    node = graph.nodes[selected]
    inside = node.polygon.buffer(graph.tolerance).covers(footprint(xy, heading, length, width))
    return {'node': selected, 'node_kind': node.kind, 'body_inside_node': bool(inside),
            'reason': 'localized', 'overlapping_nodes': len(choices)}
