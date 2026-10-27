"""Check a new merge path against unchanged original checks plus explicit reserve."""
import numpy as np
from trajectory_checks import headings,motion_check,collision_check,tangent,angle_diff
from language_selector import action_matches
from .pose_geometry import interpolate_centers_and_angles,check_poses
from .kinematic_diagnostic import inverse_center_path
from .corridor_reserve import target_reserve,margin_key


def evaluate_proposal(points,raw,center,acceleration,graph,anchor,obstacles,action,speed,geometry,margin=.1,full=False):
    reasons=[];skipped=[];detail={};length=float(center[3]);width=float(center[4]);initial=float(center[6])
    deviation=float(np.linalg.norm(points[1:]-raw,axis=1).max());detail['maximum_raw_deviation_m']=deviation
    motion=motion_check(points,center[7:9],initial_acceleration=acceleration);detail['motion']=motion
    if deviation>1.:reasons.append('raw_deviation')
    if not motion['passed']:reasons.append('motion')
    if reasons and not full:
        return {'passed':False,'rejected_by':reasons,'skipped_checks':['route','target_reserve','body','collision','inverse_geometry'],'details':detail}
    route=graph.match(points,initial,start_nodes={anchor});graph.settled_lane_changes(route,points,initial,length,width);detail['route']=route
    row={'route':route,'motion':motion}
    if not route['matched']:reasons.append('observed_start_road_route')
    if not action_matches(row,action,speed):reasons.append('settled_single_merge')
    angles=headings(points,initial);dense,original=interpolate_centers_and_angles(points,angles)
    inverse=inverse_center_path(dense,initial,**geometry,dt=.05);alternative=inverse['heading']
    detail['inverse_motion_diagnostic']=inverse['summary'];events=route.get('lane_changes',[])
    reserve=False
    if route['matched'] and len(events)==1 and events[0]['action']==action and not route.get('turns'):
        reserve=target_reserve(dense,[original,alternative],length,width,graph.forward_corridor(events[0]['to']),events[0]['step']*.1,[margin])[margin_key(margin)]
    detail['target_reserve_passed']=reserve
    if not reserve:reasons.append('target_reserve')
    if reasons and not full:
        return {'passed':False,'rejected_by':reasons,'skipped_checks':['body','collision','inverse_geometry'],'details':detail}
    body=graph.body_check(points,initial,length,width);collision=collision_check(points,initial,length,width,obstacles)
    other=check_poses(dense,alternative,length,width,graph.surface,obstacles)
    route_concerns=[]
    if route['matched']:
        route_concerns=[i*.1 for i,(p,h,key) in enumerate(zip(points,alternative[::2],route['node_sequence'])) if abs(angle_diff(h,tangent(graph.nodes[key].baseline,p)))>np.radians(60)]
    detail.update(body=body,collision=collision,inverse_geometry=other,inverse_assigned_route_heading_concerns=route_concerns)
    for passed,reason in [(body['passed'],'road_footprint'),(collision['passed'],'constant_velocity_collision'),
        (other['body_passed'],'inverse_road_footprint'),(other['cv_collision_passed'],'inverse_cv_collision'),(not route_concerns,'inverse_route_heading')]:
        if not passed:reasons.append(reason)
    return {'passed':not reasons,'rejected_by':reasons,'skipped_checks':skipped,'details':detail}
