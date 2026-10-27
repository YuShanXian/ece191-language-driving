"""Re-target an uncommitted junction from the live pose, without road snapping.

A cancelled connector is localization evidence, not permission to finish its
old turn. Only sibling exits of that incoming lane are eligible. Once a turn
has substantially begun, this forward-only re-target is no longer allowed.
"""
import math
import numpy as np
from shapely.geometry import LineString, Point
from .geometry import RoadNode, tangent, angle_diff, footprint, arc
from .junctions import connector_curve
from .routes import assemble_tail


def replan(scene, state, action):
    located = scene.locate(state)
    if not located:
        return None
    key, offset = located
    old = scene.topology.by_connector.get(key)
    if not old or old.action == action or old.road_bend:
        return None
    source = scene.nodes[old.source]
    entry_heading = tangent(source.baseline, source.baseline.coords[-1])
    # Changing an exit is possible before committing to the old turn. Do not
    # silently complete/undo an already executed left turn for a right command.
    if abs(angle_diff(state['heading'], entry_heading)) > math.radians(20):
        return None
    xy = np.asarray(state['xy']); heading = state['heading']
    forward = np.array([math.cos(heading), math.sin(heading)])
    virtual = RoadNode('live_pose', scene.graph.surface,
                       LineString([xy-forward, xy]), 'lane')
    for movement in scene.topology.options(old.source, action):
        if movement.rank_error != 0:
            continue
        connector = movement.connector; target = movement.target
        baseline = scene.nodes[connector].baseline
        at = baseline.project(Point(xy))
        target_length = min(8, scene.nodes[target].baseline.length)
        tail = scene.continuation(target, target_length)
        route = None
        # Preserve an already aligned mapped curve whenever the live pose
        # actually lies on it; never move the vehicle to that curve's origin.
        if baseline.distance(Point(xy)) <= .3:
            try:
                route = assemble_tail(scene, [(connector, at, baseline.length),
                    (target, 0, target_length)], tail, state)
                if not fits(scene, route['points'], heading):
                    route = None
            except ValueError:
                pass
        if route is None:
            curve = connector_curve(virtual, scene.nodes[target], scene.graph.surface,
                                    True, independent_tangents=True)
            if curve is None or not fits(scene, list(curve.coords), heading):
                continue
            try:
                prefix = np.asarray(curve.coords)
                route = assemble_tail(scene, [(target, 0, target_length)], tail, prefix=prefix)
                length = float(arc(prefix)[-1])
                route['segments'].insert(0, dict(node_id=connector, start=0., end=length))
                route['movements'] = scene.topology.describe(route['segments'])
            except ValueError:
                continue
        end = route['segments'][0]['end']
        route['permitted_maneuver'] = connector
        route['geometry_source'] = 'live_junction_replan'
        route['junction_replan'] = dict(previous_connector=key, incoming_lane=old.source,
            connector=connector, target=target, entry_progress_m=offset,
            start_xy=state['xy'], start_heading=heading)
        return route, 0., float(end + target_length), connector
    return None


def fits(scene, points, heading):
    """Check initial heading and the entire footprint at dense curve samples."""
    pts = np.asarray(points)
    derivatives = np.gradient(pts, axis=0)
    headings = np.arctan2(derivatives[:, 1], derivatives[:, 0])
    if abs(angle_diff(headings[0], heading)) > .08:
        return False
    return all(scene.graph.surface.covers(footprint(p, h, 4.8, 2.0))
               for p, h in zip(pts, headings))
