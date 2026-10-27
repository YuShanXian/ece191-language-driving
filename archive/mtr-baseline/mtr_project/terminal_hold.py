"""Explicit terminal policy: hold the last filtered command; never call a tracker."""
import numpy as np
from nuplan.common.actor_state.ego_state import EgoState
from nuplan.common.actor_state.dynamic_car_state import DynamicCarState
from nuplan.common.actor_state.state_representation import StateSE2,StateVector2D,TimePoint,TimeDuration
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.controller.motion_model.kinematic_bicycle import KinematicBicycleModel


def extend_hold(parent,reference,motion,dt=.05,parent_duration=5.8,target_duration=6.):
    """Copy every parent array exactly, then append original reference samples and held-control states."""
    n=round(parent_duration/dt)+1;total=round(target_duration/dt)+1
    if not (dt>0 and total>n and abs((n-1)*dt-parent_duration)<1e-10 and abs((total-1)*dt-target_duration)<1e-10):
        raise ValueError('Invalid terminal time grid')
    shapes={'time_s':(n,),'center_xy':(n,2),'heading':(n,),'target_center_xy':(n,2),'target_heading':(n,),
        'tire_angle_rad':(n,),'rear_speed_mps':(n,),'rear_acceleration_mps2':(n,),
        'commands_accel_and_tire_rate':(n-1,2),'raw_commands_accel_and_tire_rate':(n-1,2),'control_tick':(n-1,)}
    if set(parent)!=set(shapes):raise ValueError('Unexpected parent arrays')
    for key,shape in shapes.items():
        if parent[key].shape!=shape or not np.isfinite(parent[key]).all():raise ValueError('Incomplete or invalid parent: '+key)
    np.testing.assert_allclose(parent['time_s'],np.arange(n)*dt,atol=1e-12,rtol=0)
    if len(reference['time_s'])!=total:raise ValueError('Original full reference is required; extrapolation forbidden')
    np.testing.assert_allclose(reference['time_s'],np.arange(total)*dt,atol=1e-12,rtol=0)
    for key in ['target_center_xy','target_heading']:
        if not np.isfinite(reference[key]).all():raise ValueError('Nonfinite target')
        np.testing.assert_array_equal(parent[key],reference[key][:n])
    result={key:value.copy() for key,value in parent.items()}
    vehicle=get_pacifica_parameters();model=KinematicBicycleModel(vehicle,motion['max_steering_angle_rad'],0.,0.)
    applied=parent['commands_accel_and_tire_rate'][-1].copy();raw=parent['raw_commands_accel_and_tire_rate'][-1].copy()
    for i in range(n-1,total-1):
        h,tire,speed,accel=(float(result[k][-1]) for k in ['heading','tire_angle_rad','rear_speed_mps','rear_acceleration_mps2'])
        rear=result['center_xy'][-1]-vehicle.rear_axle_to_center*np.array([np.cos(h),np.sin(h)])
        state=EgoState.build_from_rear_axle(StateSE2(*rear,h),StateVector2D(speed,0.),StateVector2D(accel,0.),
            tire,TimePoint(round(i*dt*1e6)),vehicle,angular_vel=speed*np.tan(tire)/vehicle.wheel_base)
        control=DynamicCarState.build_from_rear_axle(vehicle.rear_axle_to_center,StateVector2D(speed,0.),
            StateVector2D(float(applied[0]),0.),tire_steering_rate=float(applied[1]))
        following=model.propagate_state(state,control,TimeDuration.from_s(dt))
        values={'time_s':(i+1)*dt,'center_xy':[following.center.x,following.center.y],'heading':following.center.heading,
            'target_center_xy':reference['target_center_xy'][i+1],'target_heading':reference['target_heading'][i+1],
            'tire_angle_rad':following.tire_steering_angle,'rear_speed_mps':following.dynamic_car_state.rear_axle_velocity_2d.x,
            'rear_acceleration_mps2':following.dynamic_car_state.rear_axle_acceleration_2d.x,
            'commands_accel_and_tire_rate':applied,'raw_commands_accel_and_tire_rate':raw,'control_tick':False}
        for key,value in values.items():
            if not np.isfinite(value).all():raise ValueError('Nonfinite terminal propagation')
            result[key]=np.concatenate((result[key],np.asarray(value).reshape((1,)+result[key].shape[1:])),axis=0)
    return result


def assert_terminal_contract(parent,reference,data,dt=.05):
    """Verify prefix, command hold, target and no-new-controller contract independently of propagation."""
    n=len(parent['time_s']);total=len(reference['time_s']);extra=total-n
    if extra<=0 or set(data)!=set(parent):raise ValueError('Invalid extension')
    for key in parent:
        prefix=len(parent[key])
        if data[key].shape!=(prefix+extra,)+parent[key].shape[1:]:raise ValueError('Wrong output shape')
        if not np.isfinite(data[key]).all():raise ValueError('Nonfinite extension')
        np.testing.assert_array_equal(data[key][:prefix],parent[key])
    np.testing.assert_allclose(data['time_s'],np.arange(total)*dt,atol=1e-12,rtol=0)
    for key in ['target_center_xy','target_heading']:np.testing.assert_array_equal(data[key],reference[key])
    for key in ['commands_accel_and_tire_rate','raw_commands_accel_and_tire_rate']:
        np.testing.assert_array_equal(data[key][n-1:],np.broadcast_to(parent[key][-1],(extra,2)))
    if data['control_tick'][n-1:].any():raise ValueError('Unexpected terminal controller update')
