"""Ordinary reverse follows lane geometry; history is never a routing input."""
import math
import numpy as np
from .geometry import arc, clean, validate_path, angle_diff, reverse_clearance
from .routes import trim


def reverse(scene, state, distance):
    located = scene.locate(state)
    if not located:
        raise ValueError('No current lane is available for reversing; use an explicit turnaround for recovery')
    sections = list(scene.topology.reverse_corridor(*located, limit=distance+.1))
    points, markers = [], []
    length = 0.0
    for key, start, end in sections:
        part = scene.section(key, end, start)[::-1]
        if points:
            gap = float(np.linalg.norm(points[-1]-part[0]))
            if gap > 1:
                raise ValueError('The backward lane connection is disconnected')
            length += gap
        begin = length
        length += float(arc(part)[-1])
        points.extend(part)
        markers.append(dict(node_id=key, start=begin, end=length))
    if len(points)<2 or length < distance-.02:
        raise ValueError(f'Only {length:.1f} m of continuous lane is available behind the car; '
                         'reversing farther would require a turn, lane change, ambiguous split or leaving the map')
    points = clean(points)
    original_arc = arc(points)
    offset = np.asarray(state['xy'])-points[0]
    if np.linalg.norm(offset)>.8:
        raise ValueError('The car is between lanes; a reverse must start inside its current lane')
    points += offset * np.maximum(0,1-arc(points)/10)[:,None]**3
    points[0] = state['xy']
    corrected_arc = arc(points)
    markers = [{**s, 'start':float(np.interp(s['start'],original_arc,corrected_arc)),
                'end':float(np.interp(s['end'],original_arc,corrected_arc))} for s in markers]
    route = trim(dict(points=points.tolist(), segments=markers), distance)
    valid, reason = validate_path(route['points'])
    if not valid:
        raise ValueError(reason)
    delta = np.asarray(route['points'][1])-route['points'][0]
    body = math.atan2(delta[1],delta[0])+math.pi
    if abs(angle_diff(body,state['heading']))>.35:
        raise ValueError('No reverse path preserves the current vehicle heading')
    if not reverse_clearance(route, scene.graph.surface):
        raise ValueError('The full vehicle cannot reverse within the mapped road surface')
    route.update(reverse=True, retrace_history=False, geometry_source='current_lane_reverse',
                 movements=scene.topology.describe(route['segments']))
    return route
