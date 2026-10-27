"""Connected route assembly with explicit node identity and bounded steering."""

import numpy as np
from shapely.geometry import Point
from .geometry import clean, arc, validate_path


def assemble(scene, sections, pose=None, prefix=None):
    points = [] if prefix is None else list(np.asarray(prefix))
    markers = []
    distance = arc(np.asarray(points))[-1] if len(points) > 1 else 0
    for key, start, end in sections:
        part = scene.section(key, start, end)
        if points:
            gap = float(np.linalg.norm(points[-1] - part[0]))
            if gap > 1.0:
                raise ValueError(f"Disconnected map edge before {key}: {gap:.2f} m")
            distance += gap
        begin = distance
        distance += float(arc(part)[-1])
        points.extend(part)
        markers.append({"node_id": key, "start": float(begin), "end": float(distance)})
    points = clean(points)
    if len(points) < 2:
        raise ValueError("Current lane has ended; reverse or request another maneuver")
    if pose is not None:
        gap = np.linalg.norm(np.asarray(pose["xy"]) - points[0])
        first_node = scene.nodes[sections[0][0]] if sections else None
        if gap > 2.2 or (
            gap > 0.8
            and (first_node is None or not first_node.polygon.buffer(0.1).covers(Point(pose["xy"])))
        ):
            raise ValueError("Vehicle is not inside the selected lane")
        if gap > 0.001:
            # Smoothly remove a small localization residual; never bridge to another lane.
            offset = np.asarray(pose["xy"]) - points[0]
            s = arc(points)
            points += offset * np.maximum(0, 1 - s / 15)[:, None] ** 3
        points[0] = pose["xy"]
    ok, reason = validate_path(points)
    if not ok:
        raise ValueError(reason)
    boundary = None
    if sections:
        key, _, end = sections[-1]
        at_end = end >= scene.nodes[key].baseline.length - .05
        exits = sorted({m.action for m in scene.topology.by_lane.get(key, [])})
        if at_end and not scene.topology.forward.get(key):
            boundary = dict(kind='junction' if exits else 'map_end', node_id=key, available_actions=exits)
        else:
            boundary = dict(kind='planned_limit', node_id=key, available_actions=[])
    return {
        "points": np.round(points, 4).tolist(),
        "segments": markers,
        "length": float(arc(points)[-1]),
        "stop_at_end": True,
        "movements": scene.topology.describe(markers),
        "stop_context": boundary,
    }


def follow(scene, state, limit=2800):
    located = scene.locate(state)
    if not located:
        raise ValueError(
            "Current position has no matching connected lane; reverse along the traveled path"
        )
    key, start = located
    return assemble(scene, scene.continuation(key, start, limit), state)


def turn(scene, state, action):
    located = scene.locate(state)
    if not located:
        return None
    approach = []
    distance = 0.0
    for key, start, end in scene.topology.corridor(*located, limit=1200):
        node = scene.nodes[key]
        for movement in scene.topology.options(key, action):
            connector, target = movement.connector, movement.target
            lead = approach + ([] if node.kind == "connector" else [(key, start, end)])
            begin = distance + (0 if node.kind == "connector" else end - start)
            connector_start = start if key == connector else 0
            required = lead + [(connector, connector_start, scene.nodes[connector].baseline.length),
                               (target, 0, min(8, scene.nodes[target].baseline.length))]
            completion = begin + scene.nodes[connector].baseline.length - connector_start + min(8, scene.nodes[target].baseline.length)
            tail = scene.continuation(target, min(8, scene.nodes[target].baseline.length))
            try:
                route = assemble_tail(scene, required, tail, state)
            except ValueError:
                continue
            route["permitted_maneuver"] = connector
            route["geometry_source"] = "inferred_connector" if connector.startswith("J_") else "mapped_connector"
            return route, float(begin), float(completion), connector
        approach.append((key, start, end))
        distance += end - start
    return None


def assemble_tail(scene, required, tail, pose=None, prefix=None):
    """A defective remote tail cannot invalidate an executable local maneuver."""
    try:
        return assemble(scene, required + tail, pose, prefix)
    except ValueError:
        # Validate the required maneuver first; it must never be truncated.
        valid = assemble(scene, required, pose, prefix)
        for i in range(1, len(tail) + 1):
            try:
                valid = assemble(scene, required + tail[:i], pose, prefix)
            except ValueError:
                valid["boundary_reason"] = "Mapped continuation has incompatible geometry"
                break
        return valid



def trim(route, distance):
    p = np.asarray(route["points"])
    s = arc(p)
    distance = min(float(distance), s[-1])
    if distance < 0.05:
        raise ValueError("Requested stopping point is behind the vehicle")
    end = np.array([np.interp(distance, s, p[:, j]) for j in range(2)])
    route = {
        **route,
        "points": clean(np.vstack([p[s < distance], end])).tolist(),
        "length": distance,
        "stop_at_end": True,
        "stop_context": {"kind": "requested_distance", "available_actions": []},
    }
    route["segments"] = [
        {**x, "end": min(x["end"], distance)} for x in route["segments"] if x["start"] < distance
    ]
    return route


