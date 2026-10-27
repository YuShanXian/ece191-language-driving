"""Complete unmarked junction movements using mapped intersection surfaces.

No nearest-road teleport, reversed lane, or off-road shortcut is added. Each
generated link joins an incoming lane end to an outgoing lane start in the same
intersection and passes a vehicle-footprint and steering-radius check.
"""

import math
import numpy as np
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely import prepare
from .geometry import RoadGraph, RoadNode, tangent, angle_diff, footprint
from .continuity import connection_geometry, lane_rank_error, straight_rank_error


def connector_curve(source, target, surface, corresponding=False, independent_tangents=False):
    a = np.asarray(source.baseline.coords[-1])[:2]
    b = np.asarray(target.baseline.coords[0])[:2]
    h0 = tangent(source.baseline, a)
    h1 = tangent(target.baseline, b)
    change = angle_diff(h1, h0)
    distance = np.linalg.norm(b - a)
    if distance < 3 or distance > 85:
        return None
    forward = np.array([math.cos(h0), math.sin(h0)])
    left = np.array([-forward[1], forward[0]])
    lateral = float((b - a) @ left)
    # A nearly straight movement must continue the same physical lane.
    # A broad intersection surface does not permit a diagonal multi-lane move.
    if abs(change) < math.radians(30):
        offset = abs(connection_geometry(source, target)[1])
        # Road blocks can be offset across an intersection. Permit an aligned,
        # corresponding exit (same lane rank), never a jump to an arbitrary lane.
        if offset > 1.75 and not (corresponding and offset <= min(10, distance * .18)):
            return None
    # Destination must lie on the requested side, not behind an unrelated road.
    if abs(change) < math.radians(150) and abs(change) > math.radians(30) and lateral * change < 0:
        return None
    if abs(change) < math.radians(30) and float((b - a) @ forward) < 2:
        return None
    u = np.linspace(0, 1, max(80, int(distance * 3)))[:, None]
    scales = [(f, f) for f in (.55, .8, 1.1, 1.5)]
    if independent_tangents:
        # A live pose can be much nearer the exit axis than a lane-end origin.
        # Equal endpoint tangents then miss valid bends. Keep the map-builder's
        # original search unchanged; expand only explicit live-pose replanning.
        scales += [(1.3, .55), (1.3, .8), (1.7, .7), (.55, 1.3), (.8, 1.3), (.7, 1.7)]
    for start_scale, end_scale in scales:
        v0 = distance * start_scale * forward
        v1 = distance * end_scale * np.array([math.cos(h1), math.sin(h1)])
        pts = (
            (2 * u**3 - 3 * u**2 + 1) * a
            + (u**3 - 2 * u**2 + u) * v0
            + (-2 * u**3 + 3 * u**2) * b
            + (u**3 - u**2) * v1
        )
        derivative = np.gradient(pts, axis=0)
        second = np.gradient(derivative, axis=0)
        curvature = np.abs(
            derivative[:, 0] * second[:, 1] - derivative[:, 1] * second[:, 0]
        ) / np.maximum(np.linalg.norm(derivative, axis=1) ** 3, 1e-8)
        if np.max(curvature) > math.tan(0.6) / 3.089:
            continue
        line = LineString(pts)
        if not line.is_simple or not surface.covers(line):
            continue
        headings = np.arctan2(derivative[:, 1], derivative[:, 0])
        if independent_tangents and abs(change) >= math.radians(30):
            progress = np.unwrap(headings - h0) * np.sign(change)
            if progress.min() < -math.radians(3) or progress.max() > abs(change) + math.radians(15):
                continue
        if abs(change) < math.radians(30) and max(abs(angle_diff(h, h0)) for h in headings) > math.radians(25):
            continue
        if not all(
            surface.covers(footprint(p, h, 4.8, 2.0)) for p, h in zip(pts[::3], headings[::3])
        ):
            continue
        return line
    return None


def complete_intersections(nodes, edges, junctions):
    lanes = [n for n in nodes if n.kind == "lane"]
    groups = {}
    by_key = {n.key: n for n in nodes}
    for n in lanes:
        groups.setdefault(n.lane_group, []).append(n)
    if not junctions:
        return RoadGraph(nodes, edges)
    starts = [Point(n.baseline.coords[0]) for n in lanes]
    ends = [Point(n.baseline.coords[-1]) for n in lanes]
    stree = STRtree(starts)
    etree = STRtree(ends)
    added = []
    native_connectors = [n for n in nodes if n.kind == 'connector']
    connector_tree = STRtree([n.polygon for n in native_connectors])
    for junction in junctions:
        boundary = junction.buffer(1)
        incoming = [lanes[int(i)] for i in etree.query(boundary, predicate="intersects")]
        outgoing = [lanes[int(i)] for i in stree.query(boundary, predicate="intersects")]
        # Map intersection polygons can omit the narrow entrance/exit apron.
        # Existing connected lane surfaces supply that drivable area; a missing
        # centerline must not make the physical road disappear.
        connected_surface = unary_union([junction, *[n.polygon for n in incoming + outgoing],
            *[native_connectors[int(i)].polygon for i in connector_tree.query(boundary, predicate='intersects')]]).buffer(.05)
        for source in incoming:
            existing = {
                end
                for middle, rel in edges.get(source.key, {}).items()
                if rel == "forward"
                for end, r in edges.get(middle, {}).items()
                if r == "forward"
            }
            existing_groups = set()
            for k in existing:
                if k not in by_key:
                    continue
                turn, lateral = connection_geometry(source, by_key[k])
                if (
                    abs(turn) >= math.radians(30)
                    or abs(lateral) <= 2.2
                    or lane_rank_error(source, by_key[k], groups) == 0
                ):
                    existing_groups.add(by_key[k].lane_group)
            candidate_groups = {}
            for target in outgoing:
                if (
                    target.key == source.key
                    or target.lane_group in existing_groups
                    or target.lane_group == source.lane_group
                ):
                    continue
                candidate_groups.setdefault(target.lane_group, []).append(target)
            for candidates in candidate_groups.values():
                # Keep left-to-left / right-to-right ordinal correspondence.
                # Do not add links to every lane simply because the road surface
                # is wide enough. A failed corresponding exit stays unavailable.
                straight = abs(connection_geometry(source, candidates[0])[0]) < math.radians(30)
                target = min(
                    candidates,
                    key=lambda n: (
                        (0 if abs(connection_geometry(source, n)[1]) <= 1.75 else straight_rank_error(source, n, groups, by_key, edges), abs(connection_geometry(source, n)[1]), n.key)
                        if straight
                        else (
                            lane_rank_error(source, n, groups),
                            abs(connection_geometry(source, n)[1]),
                            n.key,
                        )
                    ),
                )
                if not straight and lane_rank_error(source, target, groups) > 0:
                    continue
                key = "J_" + source.key + "_" + target.key
                if key in edges:
                    continue
                surface = connected_surface
                rank = straight_rank_error(source, target, groups, by_key, edges) if straight else lane_rank_error(source, target, groups)
                curve = connector_curve(source, target, surface, rank == 0)
                if curve is None:
                    continue
                added.append(
                    RoadNode(key, curve.buffer(1.2).intersection(surface), curve, "connector")
                )
                edges.setdefault(source.key, {})[key] = "forward"
                edges[key] = {target.key: "forward"}
    # Some unmarked straight corridors sit outside the intersection layer.
    # Recover only exits already reached by an adjacent lane in the same road
    # block. Their entire vehicle footprint must fit the existing mapped surface.
    physical_surface = unary_union([*[n.polygon for n in nodes], *junctions]).buffer(.05)
    prepare(physical_surface)
    for group in groups.values():
        exits = {target for source in group for middle,r in edges.get(source.key, {}).items()
                 if r == 'forward' for target,rel in edges.get(middle, {}).items()
                 if rel == 'forward' and target in by_key and by_key[target].kind == 'lane'}
        for source in group:
            present = {target for middle,r in edges.get(source.key, {}).items() if r == 'forward'
                       for target,rel in edges.get(middle, {}).items() if rel == 'forward'}
            for target_key in sorted(exits - present):
                target = by_key[target_key]
                angle, _ = connection_geometry(source, target)
                if abs(angle) >= math.radians(30) or straight_rank_error(source, target, groups, by_key, edges) != 0:
                    continue
                curve = connector_curve(source, target, physical_surface, corresponding=True)
                if curve is None:
                    continue
                key = 'J_' + source.key + '_' + target.key
                if key in edges:
                    continue
                added.append(RoadNode(key, curve.buffer(1.2).intersection(physical_surface), curve, 'connector'))
                edges.setdefault(source.key, {})[key] = 'forward'
                edges[key] = {target.key:'forward'}
    graph = RoadGraph(nodes + added, edges)
    graph.surface = unary_union([graph.surface, *junctions]).buffer(0.05)
    prepare(graph.surface)
    graph.generated_junction_links = len(added)
    return graph
