"""Frozen-path feedback rollout using the installed official nuPlan controller."""
import math
import numpy as np
import yaml
from nuplan.common.actor_state.ego_state import EgoState
from nuplan.common.actor_state.state_representation import StateSE2, StateVector2D, TimePoint, TimeDuration
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.controller.tracker.lqr import LQRTracker
from nuplan.planning.simulation.controller.motion_model.kinematic_bicycle import KinematicBicycleModel
from nuplan.planning.simulation.simulation_time_controller.simulation_iteration import SimulationIteration
from nuplan.planning.simulation.trajectory.interpolated_trajectory import InterpolatedTrajectory
from .kinematic_diagnostic import inverse_center_path


def load_lqr_config(path):
    """Convert scientific-notation YAML scalars exactly as the typed SDK expects."""
    config={k:v for k,v in yaml.safe_load(path.read_text()).items() if not k.startswith('_')}
    for name,value in list(config.items()):
        if name in ('q_longitudinal','r_longitudinal','q_lateral','r_lateral'):
            config[name]=[float(v) for v in value]
        elif name=='tracking_horizon':
            config[name]=int(value)
        else:
            config[name]=float(value)
    return config


def make_reference(points, initial_heading, dt=.05):
    vehicle=get_pacifica_parameters();points=np.asarray(points,float)
    inverse=inverse_center_path(points,initial_heading,vehicle.wheel_base,vehicle.rear_axle_to_center,dt=dt)
    theta=inverse['heading'];rear=inverse['rear_xy']
    velocity=np.gradient(rear,dt,axis=0)
    speed=np.sum(velocity*np.column_stack([np.cos(theta),np.sin(theta)]),axis=1)
    acceleration=np.gradient(speed,dt)
    states=[EgoState.build_from_rear_axle(StateSE2(float(p[0]),float(p[1]),float(h)),
                StateVector2D(float(v),0.),StateVector2D(float(a),0.),0.,TimePoint(round(i*dt*1e6)),vehicle)
            for i,(p,h,v,a) in enumerate(zip(rear,theta,speed,acceleration))]
    trajectory=InterpolatedTrajectory(states)
    # This invariant catches accidentally feeding body-center coordinates as rear axle.
    recovered=np.array([[s.center.x,s.center.y] for s in states])
    if not np.allclose(recovered,points,atol=1e-9,rtol=0):raise ValueError('Center/rear-axle reconstruction mismatch')
    return trajectory,theta


def track_frozen_path(points,initial_heading,center_velocity,center_acceleration,initial_tire_angle_deg,
                      controller_config,motion_config,simulation_dt=.1,reference_dt=.05):
    points=np.asarray(points,float);velocity=np.asarray(center_velocity,float);acceleration=np.asarray(center_acceleration,float)
    if velocity.shape!=(2,) or acceleration.shape!=(2,) or not np.isfinite(np.r_[velocity,acceleration,initial_tire_angle_deg]).all():raise ValueError('Invalid observed initial dynamics')
    if not math.isfinite(simulation_dt) or simulation_dt<=0:raise ValueError('Invalid integration step')
    horizon=(len(points)-1)*reference_dt;steps=round(horizon/simulation_dt)
    if not np.isclose(steps*simulation_dt,horizon,atol=1e-9,rtol=0):raise ValueError('Integration step must cover full reference')
    vehicle=get_pacifica_parameters();trajectory,reference_heading=make_reference(points,initial_heading,reference_dt)
    tracker=LQRTracker(**controller_config,vehicle=vehicle)
    model=KinematicBicycleModel(vehicle,max_steering_angle=motion_config['max_steering_angle_rad'],
                              accel_time_constant=motion_config['accel_time_constant_seconds'],
                              steering_angle_time_constant=motion_config['steering_angle_time_constant_seconds'])
    tire=math.radians(initial_tire_angle_deg)
    if abs(tire)>motion_config['max_steering_angle_rad']:raise ValueError('Initial tire angle exceeds model limit')
    direction=np.array([math.cos(initial_heading),math.sin(initial_heading)])
    speed=float(np.dot(velocity,direction));yaw_rate=speed*math.tan(tire)/vehicle.wheel_base
    rear_accel=float(np.dot(acceleration,direction)+vehicle.rear_axle_to_center*yaw_rate*yaw_rate)
    rear_xy=points[0]-vehicle.rear_axle_to_center*direction
    state=EgoState.build_from_rear_axle(StateSE2(*rear_xy,initial_heading),StateVector2D(speed,0.),
                StateVector2D(rear_accel,0.),tire,TimePoint(0),vehicle,angular_vel=yaw_rate)
    states=[state];commands=[]
    for i in range(steps):
        current=SimulationIteration(TimePoint(round(i*simulation_dt*1e6)),i)
        next_iteration=SimulationIteration(TimePoint(round((i+1)*simulation_dt*1e6)),i+1)
        control=tracker.track_trajectory(current,next_iteration,state,trajectory)
        commands.append([control.rear_axle_acceleration_2d.x,control.tire_steering_rate])
        state=model.propagate_state(state,control,TimeDuration.from_s(simulation_dt));states.append(state)
    centers=np.array([[s.center.x,s.center.y] for s in states]);headings=np.array([s.center.heading for s in states])
    times=np.arange(steps+1)*simulation_dt;reference_times=np.arange(len(points))*reference_dt
    target=np.column_stack([np.interp(times,reference_times,points[:,i]) for i in [0,1]])
    target_heading=np.interp(times,reference_times,np.unwrap(reference_heading))
    error=np.linalg.norm(centers-target,axis=1);angle_error=np.arctan2(np.sin(headings-target_heading),np.cos(headings-target_heading))
    tire_angles=np.array([s.tire_steering_angle for s in states]);speeds=np.array([s.dynamic_car_state.rear_axle_velocity_2d.x for s in states])
    accelerations=np.array([s.dynamic_car_state.rear_axle_acceleration_2d.x for s in states]);commands=np.asarray(commands)
    arrays={'time_s':times,'center_xy':centers,'heading':headings,'target_center_xy':target,'target_heading':target_heading,
            'tire_angle_rad':tire_angles,'rear_speed_mps':speeds,'rear_acceleration_mps2':accelerations,'commands_accel_and_tire_rate':commands}
    if any(not np.isfinite(a).all() for a in arrays.values()):raise ValueError('Nonfinite controller result')
    metrics={'rms_center_error_m':float(np.sqrt(np.mean(error**2))),'maximum_center_error_m':float(error.max()),'final_center_error_m':float(error[-1]),
             'maximum_heading_error_deg':float(np.degrees(np.abs(angle_error)).max()),'peak_abs_tire_angle_deg':float(np.degrees(np.abs(tire_angles)).max()),
             'peak_abs_tire_rate_deg_per_s':float(np.degrees(np.abs(np.diff(tire_angles)/simulation_dt)).max()),
             'peak_abs_acceleration_mps2':float(np.abs(accelerations).max()),'minimum_speed_mps':float(speeds.min()),
             'reverse_speed_samples':int((speeds<-.001).sum()),'model_steering_clamp_samples':int(np.isclose(np.abs(tire_angles),motion_config['max_steering_angle_rad'],rtol=0,atol=1e-8).sum()),
             'initial_projected_rear_speed_mps':speed,'observed_initial_center_lateral_speed_mps':float(np.dot(velocity,[-direction[1],direction[0]])),
             'assumed_initial_center_lateral_speed_mps':float(vehicle.rear_axle_to_center*yaw_rate)}
    return arrays,metrics
