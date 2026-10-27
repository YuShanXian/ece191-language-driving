"""Lateral maneuvers between paired continuous lanes.

Topology supplies lane correspondence. Geometry must separately prove that the
lanes stay side by side, the vehicle fits, and the route joins without a jump.
Every rejection is recorded so an unavailable maneuver is diagnosable.
"""
from dataclasses import dataclass
import numpy as np
from shapely.geometry import Point, LineString
from .geometry import clean, arc, footprint, validate_path, tangent, angle_diff
import math
from .routes import assemble, assemble_tail, follow


@dataclass
class Corridor:
    scene: object
    sections: list
    line: object

    @classmethod
    def from_lane(cls, scene, key, start, length):
        sections = scene.continuation(key, start, length)
        points = []
        for node, begin, end in sections:
            part = scene.section(node, begin, end)
            if points and np.linalg.norm(points[-1] - part[0]) > 1:
                raise ValueError('Adjacent lane corridor has disconnected map segments')
            points.extend(part)
        points = clean(points)
        if len(points) < 2:
            raise ValueError('Adjacent lane corridor has ended')
        return cls(scene, sections, LineString(points))

    def position(self, distance):
        remaining = distance
        previous = None
        for key, start, end in self.sections:
            part = self.scene.section(key, start, end)
            gap = np.linalg.norm(previous-part[0]) if previous is not None else 0
            remaining = max(0, remaining-gap)
            length = float(arc(part)[-1])
            if remaining <= length + 1e-6:
                return key, min(end, start+remaining)
            remaining -= length
            previous = part[-1]
        raise ValueError('Requested lane-change endpoint exceeds the adjacent corridor')


def transition(scene, state, key, start, target, stage, length=None):
    node = scene.nodes[key]
    entry = scene.topology.by_connector.get(key)
    lane = scene.nodes[entry.source] if entry else node
    target_entry = scene.topology.by_connector.get(target)
    target_lane = scene.nodes[target_entry.source] if target_entry else scene.nodes[target]
    lane_delta = (target_lane.lane_index or 1) - (lane.lane_index or 1)
    required = max(25, abs(lane_delta)*23) if length is None else float(length)
    if required < 15 or abs(lane_delta) != 1 and length is not None:
        raise ValueError('Turn preparation must be one adjacent lane with at least 15 m')
    source = Corridor.from_lane(scene, key, start, required+3)
    if source.line.length < required+1:
        raise ValueError('Current lane has insufficient continuous distance for the maneuver')
    target_start = scene.nodes[target].baseline.project(source.line.interpolate(0))
    destination = Corridor.from_lane(scene, target, target_start, required+30)
    if node.kind == 'lane' and node.baseline.length-start < required:
        source_next = scene.topology.forward.get(key, [])
        target_next = scene.topology.forward.get(target, [])
        sm = scene.topology.by_connector.get(source_next[0]) if source_next else None
        tm = scene.topology.by_connector.get(target_next[0]) if target_next else None
        if sm and tm and sm.target == tm.target:
            raise ValueError('Both lanes merge into the same exit; this would change lanes and return')
    distances = np.linspace(0, required, int(required*2)+1)
    points = np.array([source.line.interpolate(float(d)).coords[0] for d in distances])
    target_s = np.array([destination.line.project(Point(p)) for p in points])
    if np.min(np.diff(target_s)) < .05 or target_s[-1] > destination.line.length-.5:
        raise ValueError('Adjacent lane does not extend alongside the complete maneuver')
    paired = np.array([destination.line.interpolate(float(d)).coords[0] for d in target_s])
    tangent = np.gradient(points, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1)[:,None]
    offset = paired-points
    lateral = tangent[:,0]*offset[:,1] - tangent[:,1]*offset[:,0]
    expected_sign = 1 if lane_delta < 0 else -1
    # Physical correspondence must persist, not merely look adjacent at entry.
    if lane_delta == 0 or np.any(lateral*expected_sign < 1.3):
        raise ValueError('Candidate lanes merge, cross, or are on the wrong side')
    if np.any(np.linalg.norm(offset,axis=1) > 5.5*abs(lane_delta)):
        raise ValueError('Candidate is another road rather than an adjacent lane')
    u = np.linspace(0,1,len(points))
    blend = 10*u**3 - 15*u**4 + 6*u**5
    curve = points + offset*blend[:,None]
    if state is not None:
        residual = np.asarray(state['xy'])-curve[0]
        if np.linalg.norm(residual) > 2.2 or not node.polygon.buffer(.1).covers(Point(state['xy'])):
            raise ValueError('Vehicle is not inside the source lane')
        curve += residual*(1-blend)[:,None]
    valid, reason = validate_path(curve)
    if not valid:
        raise ValueError(reason)
    headings = np.arctan2(*np.gradient(curve,axis=0)[:,::-1].T)
    if not scene.graph.surface.covers(LineString(curve)) or not all(
            scene.graph.surface.covers(footprint(p,h,4.8,2.0))
            for p,h in zip(curve[::2],headings[::2])):
        raise ValueError('Vehicle footprint leaves the mapped drivable surface')
    end_key, end_offset = destination.position(float(target_s[-1]))
    return curve, end_key, end_offset, dict(
        entry_lane=lane.key, target_entry_lane=target_lane.key,
        source_corridor=key, target_corridor=target, lane_delta=lane_delta,
        lateral_start_m=float(lateral[0]), lateral_end_m=float(lateral[-1]))


def lane_change(scene, state, stage, max_approach=200, diagnostics=None):
    diagnostics = diagnostics if diagnostics is not None else {}
    diagnostics.update(candidate_count=0, rejections=[])
    located = scene.locate(state)
    if not located:
        diagnostics['reason'] = 'Vehicle could not be localized on the map'
        return None
    lead, distance = [], 0.0
    for key,start,end in scene.topology.corridor(*located,limit=max_approach):
        targets = scene.topology.lateral_options(key,stage)
        for target in targets:
            diagnostics['candidate_count'] += 1
            if target == key:
                return follow(scene,state),0,0,target
            try:
                curve,end_key,end_offset,proof = transition(
                    scene,state if not lead else None,key,start,target,stage)
                lead_route = assemble(scene,lead,state) if lead else {'points':[state['xy']],'segments':[]}
                prefix = lead_route['points']
                if np.linalg.norm(np.asarray(prefix[-1])-curve[0]) > .15:
                    raise ValueError('Approach does not join the lane change continuously')
                prefix = list(prefix)+curve[1:].tolist()
                completion = float(arc(np.asarray(prefix))[-1])
                route = assemble_tail(scene,[],scene.continuation(end_key,end_offset),prefix=prefix)
                route['segments'] = lead_route['segments'] + [{'node_id':key,'start':distance,'end':completion}] + route['segments']
                route['movements'] = scene.topology.describe(lead_route['segments']) + route.get('movements',[])
                route['lane_change'] = dict(source=key,target=end_key,start=distance,end=completion,**proof)
                return route,float(distance),completion,end_key
            except ValueError as error:
                diagnostics['rejections'].append(dict(source=key,target=target,reason=str(error)))
        lead.append((key,start,end))
        distance += end-start
    if not diagnostics['candidate_count']:
        diagnostics['reason'] = 'No adjacent lane on the reachable corridor'
        if stage['action'] in ('lane_change_left','lane_change_right'):
            side=1 if stage['action']=='lane_change_left' else -1
            h=state['heading'];left=np.array([-math.sin(h),math.cos(h)])
            opposite=[]
            for i in scene.tree.query(Point(state['xy']).buffer(6),predicate='intersects'):
                other=scene.nodes[scene.keys[int(i)]]
                if other.kind!='lane':continue
                point=other.baseline.interpolate(other.baseline.project(Point(state['xy'])))
                offset=np.asarray(point.coords[0])-state['xy']
                if 1.3<float(offset@left)*side<6 and abs(angle_diff(tangent(other.baseline,point),h))>math.radians(150):
                    opposite.append(other.key)
            if opposite:
                diagnostics.update(code='opposing_lane_only',opposing_lanes=opposite,
                    reason='The adjacent line is an opposing-traffic lane, not an executable lane change. Request a U-turn to change travel direction.')
    return None
