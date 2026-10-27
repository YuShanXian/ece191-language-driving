"""Sampled contacts with map stop polygons, without a legal crossing interpretation."""
import numpy as np
from shapely.geometry import Point,LineString
from trajectory_checks import footprint


def contact_intervals(mask,dt):
    flags=np.asarray(mask,dtype=bool)
    if flags.ndim!=1 or len(flags)<2 or not np.isfinite(dt) or dt<=0:raise ValueError('Invalid sampled contacts')
    runs=[];start=None
    for i,present in enumerate(np.r_[flags,False]):
        if present and start is None:start=i
        elif not present and start is not None:
            end=i-1
            runs.append(dict(first_sample_time_s=start*dt,last_sample_time_s=end*dt,
                kind='already_intersecting_at_anchor' if start==0 else 'new_sampled_contact',
                onset_interval_s=None if start==0 else [(start-1)*dt,start*dt]))
            start=None
    return dict(intersects_at_anchor=bool(flags[0]),sample_count=int(flags.sum()),runs=runs,
        first_later_contact_interval_s=next((r['onset_interval_s'] for r in runs if r['kind']=='new_sampled_contact'),None))


def sampled_contacts(points,angles,length,width,polygon,dt=.05):
    points=np.asarray(points,float);angles=np.asarray(angles,float)
    if points.shape!=(len(angles),2) or len(points)<2 or not np.isfinite(points).all() or not np.isfinite(angles).all():
        raise ValueError('Invalid path')
    if not all(np.isfinite(v) and v>0 for v in [length,width,dt]) or polygon.is_empty or not polygon.is_valid or polygon.geom_type not in ['Polygon','MultiPolygon']:
        raise ValueError('Invalid dimensions or region geometry')
    masks={k:[] for k in ['center','front_edge','body']}
    for xy,h in zip(points,angles):
        forward=np.array([np.cos(h),np.sin(h)]);left=np.array([-np.sin(h),np.cos(h)])
        front=xy+length/2*forward
        masks['center'].append(polygon.intersects(Point(xy)))
        masks['front_edge'].append(polygon.intersects(LineString([front-width/2*left,front+width/2*left])))
        masks['body'].append(polygon.intersects(footprint(xy,h,length,width)))
    return {key:contact_intervals(mask,dt) for key,mask in masks.items()}
