"""Inverse rear-axle bicycle diagnostic for a piecewise-linear body-center path.

This is a geometric requirement estimate, not a tracking controller or a test of
actuator feasibility. No recorded future is needed by inverse_center_path.
"""
import math
import numpy as np


def inverse_center_path(points, initial_heading, wheel_base, rear_axle_to_center,
                        dt=.1, minimum_speed=.5, integration_step=.005):
    points=np.asarray(points,dtype=float)
    values=[initial_heading,wheel_base,rear_axle_to_center,dt,minimum_speed,integration_step]
    if points.ndim!=2 or points.shape[1]!=2 or len(points)<3 or not np.isfinite(points).all():
        raise ValueError('At least three finite planar center positions required')
    if not all(math.isfinite(float(x)) for x in values) or min(values[1:])<=0:
        raise ValueError('Positive finite geometry, times and speed threshold required')
    # c = r + d*[cos(theta),sin(theta)]. Zero rear-axle lateral slip implies
    # theta_dot = center_velocity dot [-sin(theta),cos(theta)] / d.
    # rear_speed = center_velocity dot [cos(theta),sin(theta)], and
    # tan(front_tire_angle) = wheel_base * theta_dot / rear_speed.
    steps=2*math.ceil(dt/integration_step/2);h=dt/steps
    theta=float(initial_heading);angles=[theta];midpoints=[]
    velocity=np.diff(points,axis=0)/dt
    for vx,vy in velocity:
        def rate(a):return (-vx*math.sin(a)+vy*math.cos(a))/rear_axle_to_center
        for j in range(steps):
            k1=rate(theta);k2=rate(theta+h*k1/2);k3=rate(theta+h*k2/2);k4=rate(theta+h*k3)
            theta+=h*(k1+2*k2+2*k3+k4)/6
            if j+1==steps//2:midpoints.append(theta)
        angles.append(theta)
    angles=np.asarray(angles);midpoints=np.asarray(midpoints)
    rear_speed=velocity[:,0]*np.cos(midpoints)+velocity[:,1]*np.sin(midpoints)
    yaw_rate=(-velocity[:,0]*np.sin(midpoints)+velocity[:,1]*np.cos(midpoints))/rear_axle_to_center
    valid=rear_speed>=minimum_speed
    steering=np.full(len(velocity),np.nan)
    steering[valid]=np.arctan(wheel_base*yaw_rate[valid]/rear_speed[valid])
    rate_valid=valid[:-1]&valid[1:]
    steering_rate=np.diff(steering)/dt
    def peak(array,mask):return float(np.max(np.abs(array[mask]))) if np.any(mask) else None
    steer_peak=peak(np.degrees(steering),valid)
    return {'heading':angles,'rear_xy':points-rear_axle_to_center*np.column_stack([np.cos(angles),np.sin(angles)]),
        'rear_speed':rear_speed,'yaw_rate':yaw_rate,'steering_rad':steering,'steering_valid':valid,
        'summary':{'segments':len(valid),'forward_evaluable_segments':int(valid.sum()),
            'low_or_reverse_speed_segments':int((~valid).sum()),'reverse_segments':int((rear_speed<-.001).sum()),
            'steering_rate_evaluable_pairs':int(rate_valid.sum()),
            'peak_abs_front_tire_angle_deg':steer_peak,
            'peak_abs_front_tire_rate_deg_per_s':peak(np.degrees(steering_rate),rate_valid),
            'peak_abs_yaw_rate_deg_per_s':peak(np.degrees(yaw_rate),valid),
            'peak_abs_rear_lateral_acceleration_mps2':peak(rear_speed*yaw_rate,valid),
            'minimum_rear_speed_mps':float(rear_speed.min())}}
