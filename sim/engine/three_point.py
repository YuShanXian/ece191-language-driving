"""Bounded three-point turns with explicit stops at every gear change."""
import math
import numpy as np
from scipy.optimize import least_squares
from shapely.geometry import Point, box
from .geometry import arc, heading, tangent, angle_diff, footprint, validate_path
from .routes import assemble_tail
from .intent import validate_intent


def end_pose(xy, yaw, angles, radius, side):
    x,y=xy
    for angle,gear in zip(angles,(1,-1,1)):
        curvature=side*gear/radius;end=yaw+side*angle
        x+=(math.sin(end)-math.sin(yaw))/curvature
        y-=(math.cos(end)-math.cos(yaw))/curvature
        yaw=end
    return x,y,yaw


def paths(xy, yaw, angles, radius, side):
    point=np.asarray(xy);result=[]
    for angle,gear in zip(angles,(1,-1,1)):
        curvature=side*gear/radius;length=gear*radius*angle
        travel=np.linspace(0,length,max(3,int(abs(length)/.2)+1))
        headings=yaw+curvature*travel
        points=np.column_stack([point[0]+(np.sin(headings)-math.sin(yaw))/curvature,
                                point[1]-(np.cos(headings)-math.cos(yaw))/curvature])
        result.append((points,headings,gear));point=points[-1];yaw=headings[-1]
    return result


def three_point(scene, state, reverse_route):
    from .recovery import reverse_clearance
    x,y=state['xy'];surface=scene.graph.surface.intersection(box(x-55,y-55,x+55,y+55))
    trials=0
    for back in (3,5,8,12,18):
        try:retreat=reverse_route(scene,state,back)
        except ValueError:continue
        if not reverse_clearance(retreat,surface):continue
        a=retreat['points'][-1];h=heading(retreat['points'],True)+math.pi
        candidates=[]
        for i in scene.tree.query(Point(a).buffer(15),predicate='intersects'):
            key=scene.keys[int(i)];node=scene.nodes[key]
            if node.kind!='lane':continue
            offset=node.baseline.project(Point(a));point=node.baseline.interpolate(offset)
            if abs(angle_diff(tangent(node.baseline,point),h))<math.radians(155):continue
            candidates.append((node.baseline.distance(Point(a)),key,offset))
        for _,key,offset in sorted(candidates)[:4]:
            line=scene.nodes[key].baseline
            for delta in (0,-2,2,-4,4,-8,8):
                at=max(3,min(line.length-8,offset+delta))
                if at<0:continue
                b=np.asarray(line.interpolate(at).coords[0]);h1=tangent(line,b)
                for radius in (4.8,5.5,6.5):
                    for side in (1,-1):
                        trials+=1
                        if trials>500:return None
                        def residual(angles):
                            px,py,ph=end_pose(a,h,angles,radius,side)
                            return [px-b[0],py-b[1],radius*angle_diff(ph,h1)]
                        solved=least_squares(residual,[1.25,.65,1.25],
                            bounds=([.15,.15,.15],[1.6,2.8,1.6]),max_nfev=35)
                        if np.linalg.norm(solved.fun)>.015:continue
                        curves=paths(a,h,solved.x,radius,side)
                        if not all(validate_path(p)[0] and all(surface.covers(footprint(x,y,4.8,2))
                            for x,y in zip(p,hs)) for p,hs,g in curves):continue
                        tag='RECOVERY_'+key;phases=[dict(route=retreat,completion_m=retreat['length'],
                            maneuver_start_m=0,speed_limit_mps=1.5,stop_at_end=True,
                            reason=f'Reverse {back} m to make room for a three-point turn; stop before changing gear.')]
                        try:
                            for index,(p,hs,gear) in enumerate(curves):
                                length=float(arc(p)[-1]);last=index==2
                                if last:
                                    route=assemble_tail(scene,[],scene.continuation(key,at),prefix=p)
                                    completion=length+min(8,route['length']-length)
                                    if completion-length<3:raise ValueError('Opposing exit too short')
                                else:
                                    route=dict(points=p.tolist(),segments=[],length=length,stop_at_end=True,movements=[])
                                    completion=length
                                route['reverse']=gear<0
                                route['retrace_history']=False
                                route['geometry_source']='recovery_three_point'
                                if gear>0:
                                    route['movements'].insert(0,dict(connector=tag,source=state.get('node_id'),
                                        target=key,action='u_turn',road_bend=False,start=0,end=length))
                                validate_intent(route,'u_turn',tag)
                                phases.append(dict(route=route,completion_m=completion,maneuver_start_m=0,
                                    speed_limit_mps=1.5 if gear<0 else 3,stop_at_end=not last,
                                    reason=('Finish the three-point turn into the mapped opposing lane.' if last else
                                      'Three-point turn: '+('reverse' if gear<0 else 'forward')+' steering; stop before changing gear.')))
                            return dict(status='ready',phases=phases,route=phases[0]['route'],route_source=tag,
                                recovery=dict(kind='three_point',reverse_m=back,target_node=key,
                                    radius_m=radius,angles=solved.x.tolist(),side=side,gear_changes=3,
                                    max_curvature=1/radius,vehicle_length=4.8,vehicle_width=2),
                                **{k:v for k,v in phases[0].items() if k!='route'})
                        except ValueError:continue
    return None
