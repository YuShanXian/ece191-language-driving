"""Geometry diagnostic with explicit body headings, supplied in center coordinates."""
import numpy as np
from trajectory_checks import footprint


def check_poses(points,angles,length,width,surface,obstacles,dt=.05):
    points=np.asarray(points,float);angles=np.asarray(angles,float)
    if points.ndim!=2 or points.shape[1]!=2 or angles.shape!=(len(points),) or len(points)<2:
        raise ValueError('Matching planar positions and headings required')
    if not np.isfinite(points).all() or not np.isfinite(angles).all() or not all(np.isfinite(x) and x>0 for x in [length,width,dt]):
        raise ValueError('Finite poses and positive dimensions/time required')
    outside=[];first_hits=[];max_outside_area=0.
    for i,(position,angle) in enumerate(zip(points,angles)):
        body=footprint(position,angle,length,width)
        if not surface.covers(body):
            outside.append(i*dt)
            max_outside_area=max(max_outside_area,float(body.difference(surface).area))
        if first_hits:continue
        padded=footprint(position,angle,length,width,.2)
        for actor in obstacles:
            other=np.asarray(actor['xy'])+np.asarray(actor['velocity'])*(i*dt)
            if np.linalg.norm(position-other)>length+actor['length']+2:continue
            if padded.intersects(footprint(other,actor['heading'],actor['length'],actor['width'],.2)):
                first_hits.append({'time_sec':i*dt,'object_id':actor['id'],'category':actor['category']})
    return {'body_passed':not outside,'outside_times_seconds':outside,'maximum_outside_area_m2':max_outside_area,
        'cv_collision_passed':not first_hits,'first_hits':first_hits}


def interpolate_centers_and_angles(points,angles):
    """Original 0.1s endpoint/midpoint screen, represented as explicit 0.05s poses."""
    points=np.asarray(points,float);angles=np.asarray(angles,float)
    dense=np.empty((len(points)*2-1,2));dense[::2]=points;dense[1::2]=(points[:-1]+points[1:])/2
    headings=np.empty(len(dense));headings[::2]=angles
    delta=np.arctan2(np.sin(np.diff(angles)),np.cos(np.diff(angles)))
    headings[1::2]=angles[:-1]+delta/2
    return dense,headings
