"""Bounded reverse-assisted turnaround on mapped drivable space.

Search actual opposite-direction lanes, not a mirrored or invented destination.
Each gear has its own continuous trajectory and must stop before a gear change.
"""
import math
import numpy as np
from shapely.geometry import Point, LineString, box
from .geometry import arc, clean, heading, tangent, angle_diff, footprint, validate_path, reverse_clearance
from .routes import assemble_tail, trim


def curve(a, h0, b, h1, surface):
    a, b = np.asarray(a), np.asarray(b)
    distance = np.linalg.norm(b-a)
    if not 7 < distance < 35:
        return None
    u = np.linspace(0,1,max(100,int(distance*5)))[:,None]
    for factor in (1.6,1.8,2.0,2.3,2.6,3.0):
        v0 = distance*factor*np.array([math.cos(h0),math.sin(h0)])
        v1 = distance*factor*np.array([math.cos(h1),math.sin(h1)])
        p = (2*u**3-3*u**2+1)*a+(u**3-2*u**2+u)*v0+(-2*u**3+3*u**2)*b+(u**3-u**2)*v1
        d = np.gradient(p,axis=0); dd=np.gradient(d,axis=0)
        k=np.abs(d[:,0]*dd[:,1]-d[:,1]*dd[:,0])/np.maximum(np.linalg.norm(d,axis=1)**3,1e-8)
        if k.max()>.215 or not LineString(p).is_simple or not surface.covers(LineString(p)):
            continue
        hs=np.arctan2(d[:,1],d[:,0])
        if all(surface.covers(footprint(x,h,4.8,2)) for x,h in zip(p,hs)) and validate_path(p)[0]:
            return p,float(k.max())
    return None


def turnaround(scene, state, reverse_route):
    x,y=state['xy']
    surface=scene.graph.surface.intersection(box(x-90,y-90,x+90,y+90))
    for back in (0,3,5,8,12,18,25):
        reverse=None
        if back:
            try:
                reverse=reverse_route(scene,state,back)
            except ValueError:
                continue
            if not reverse_clearance(reverse,surface):
                continue
            a=reverse['points'][-1]
            h0=heading(reverse['points'],True)+math.pi
        else:a=state['xy'];h0=state['heading']
        candidates=[]
        for i in scene.tree.query(Point(a).buffer(28),predicate='intersects'):
            key=scene.keys[int(i)];node=scene.nodes[key]
            if key.startswith('J_'):
                continue
            offset=node.baseline.project(Point(a))
            h1=tangent(node.baseline,node.baseline.interpolate(offset))
            if abs(angle_diff(h1,h0))<math.radians(155):
                continue
            for delta in (0,-3,3,-6,6):
                s=max(0,min(node.baseline.length,offset+delta))
                b=list(node.baseline.interpolate(s).coords[0])[:2]
                candidates.append((np.linalg.norm(np.asarray(b)-a),key,s,b,h1))
        for _,key,s,b,h1 in sorted(candidates):
            found=curve(a,h0,b,h1,surface)
            if not found:
                continue
            points,curvature=found
            try:
                tail=scene.continuation(key,s)
                route=assemble_tail(scene,[],tail,prefix=points)
                length=float(arc(points)[-1])
                if route['length']-length<5:
                    continue
                tag='RECOVERY_'+key
                route['movements']=[dict(connector=tag,source=state.get('node_id'),target=key,
                    action='u_turn',road_bend=False,start=0,end=length)]+route.get('movements',[])
                route['permitted_maneuver']=tag
                route['geometry_source']='recovery_turn'
                # No extra junction turn may hide in the continuation.
                from .intent import validate_intent
                validate_intent(route,'u_turn',tag)
                phases=[]
                if reverse:
                    phases.append(dict(route=reverse,completion_m=reverse['length'],maneuver_start_m=0,
                        speed_limit_mps=1.5,stop_at_end=True,reason=f'Reverse {back} m along the traveled path; stop before turning.'))
                phases.append(dict(route=route,completion_m=length+min(8,route['length']-length),
                    maneuver_start_m=0,speed_limit_mps=3.0,reason='Turn around into the mapped opposing lane, then continue in that lane.'))
                return dict(status='ready',phases=phases,route=phases[0]['route'],
                    route_source=tag,recovery=dict(reverse_m=back,target_node=key,max_curvature=curvature,
                        vehicle_length=4.8,vehicle_width=2.0),**{k:v for k,v in phases[0].items() if k!='route'})
            except ValueError:
                continue
    from .three_point import three_point
    return three_point(scene,state,reverse_route)


def reverse_history(scene, state, distance):
    history = clean(state.get("history", [])) if state.get("history") else np.empty((0, 2))
    retrace = False
    if len(history) > 1:
        # Project onto the traveled polyline, not its nearest sample. After a
        # reverse, the closest sample can lie a few centimeters ahead and would
        # create a forward-then-backward cusp in the next reverse command.
        traveled = arc(history)
        progress = LineString(history).project(Point(state['xy']))
        p = clean([state['xy'], *history[traveled < progress - .001][::-1]])
        if len(p) > 1:
            tangent = p[1] - p[0]
            body = math.atan2(tangent[1], tangent[0]) + math.pi
            retrace = bool(arc(p)[-1] >= distance - .15 and
                abs(math.atan2(math.sin(body-state['heading']), math.cos(body-state['heading']))) <= .35)
    if not retrace:
        # A mapped reverse has no forward trail. Old sessions may have saved
        # that backward leg as history; reversing it again points the body in
        # the opposite direction and cannot be installed by the vehicle.
        located = scene.locate(state)
        if not located:
            raise ValueError("No traveled path available for reversing")
        key, s = located
        p = scene.section(key, max(0, s - distance), s)[::-1]
    if len(p) < 2 or arc(p)[-1] < distance - 0.15:
        raise ValueError("The recorded connected path is too short for this reverse distance")
    offset = np.asarray(state["xy"]) - p[0]
    if np.linalg.norm(offset) > 0.8:
        raise ValueError("No connected reverse path starts at the current position")
    p += offset * np.maximum(0, 1 - arc(p) / 10)[:, None] ** 3
    p[0] = state["xy"]
    route = trim({"points": p.tolist(), "segments": []}, distance)
    valid, reason = validate_path(route["points"])
    if not valid:
        raise ValueError(reason)
    tangent = np.asarray(route['points'][1]) - route['points'][0]
    body = math.atan2(tangent[1], tangent[0]) + math.pi
    if abs(math.atan2(math.sin(body-state['heading']), math.cos(body-state['heading']))) > .35:
        raise ValueError("No reverse path preserves the current vehicle heading")
    route["reverse"] = True
    route["retrace_history"] = retrace
    route["geometry_source"] = "traveled_path" if retrace else "mapped_reverse"
    return route


