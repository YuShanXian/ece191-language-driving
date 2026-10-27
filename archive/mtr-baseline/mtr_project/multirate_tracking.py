"""Separate feedback timing from kinematic substeps without changing old evidence.

sdk_substep: hold the ideal command, calling the SDK's actuator filter at each
motion substep. Its steering-rate attenuation explicitly depends on that step.
control_period_filter: apply the same discrete actuator update once per control
period, then hold the resulting acceleration/rate through zero-delay kinematic
substeps. This is a diagnostic discretization, not a calibrated actuator model.
"""
import math
import numpy as np
from nuplan.common.actor_state.dynamic_car_state import DynamicCarState
from nuplan.common.actor_state.ego_state import EgoState
from nuplan.common.actor_state.state_representation import StateSE2, StateVector2D, TimePoint, TimeDuration
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.controller.tracker.lqr import LQRTracker
from nuplan.planning.simulation.controller.motion_model.kinematic_bicycle import KinematicBicycleModel
from nuplan.planning.simulation.simulation_time_controller.simulation_iteration import SimulationIteration
from .tracking_diagnostic import make_reference


MODES = ('sdk_substep', 'control_period_filter')


def timing_grid(horizon, control_dt, integration_dt):
    values = [horizon, control_dt, integration_dt]
    if not all(math.isfinite(x) and x > 0 for x in values):
        raise ValueError('Finite positive times required')
    for value in values:
        if not np.isclose(value * 1e6, round(value * 1e6), atol=1e-7, rtol=0):
            raise ValueError('Times must use integral microseconds')
    stride = round(control_dt / integration_dt)
    steps = round(horizon / integration_dt)
    if stride < 1 or not np.isclose(stride * integration_dt, control_dt, atol=1e-10, rtol=0):
        raise ValueError('Control period must contain an integral number of motion steps')
    if steps < stride or steps % stride or not np.isclose(steps * integration_dt, horizon, atol=1e-10, rtol=0):
        raise ValueError('Full reference must contain complete control periods')
    return steps, stride


def effective_motion_config(motion_config, mode):
    if mode not in MODES:
        raise ValueError('Unknown actuator schedule')
    return dict(motion_config) if mode == 'sdk_substep' else {
        **motion_config, 'accel_time_constant_seconds': 0., 'steering_angle_time_constant_seconds': 0.}


def filtered_command(command, acceleration, control_dt, motion_config):
    """The SDK's discrete update, evaluated at the declared control period."""
    accel_gain = control_dt / (control_dt + motion_config['accel_time_constant_seconds'])
    steer_gain = control_dt / (control_dt + motion_config['steering_angle_time_constant_seconds'])
    return np.array([acceleration + accel_gain * (command[0] - acceleration), steer_gain * command[1]])


def track_multirate_path(points, initial_heading, center_velocity, center_acceleration,
                         initial_tire_angle_deg, controller_config, motion_config,
                         control_dt=.1, integration_dt=.025, mode='control_period_filter', reference_dt=.05):
    points = np.asarray(points, float)
    velocity = np.asarray(center_velocity, float)
    acceleration = np.asarray(center_acceleration, float)
    if velocity.shape != (2,) or acceleration.shape != (2,) or not np.isfinite(np.r_[velocity, acceleration, initial_tire_angle_deg]).all():
        raise ValueError('Invalid observed initial dynamics')
    horizon = (len(points) - 1) * reference_dt
    steps, stride = timing_grid(horizon, control_dt, integration_dt)
    if not all(math.isfinite(v) and v >= 0 for v in motion_config.values()) or motion_config['max_steering_angle_rad'] <= 0:
        raise ValueError('Invalid motion parameters')
    effective = effective_motion_config(motion_config, mode)
    vehicle = get_pacifica_parameters()
    trajectory, reference_heading = make_reference(points, initial_heading, reference_dt)
    tracker = LQRTracker(**controller_config, vehicle=vehicle)
    model = KinematicBicycleModel(vehicle, effective['max_steering_angle_rad'],
                                 effective['accel_time_constant_seconds'], effective['steering_angle_time_constant_seconds'])
    tire = math.radians(initial_tire_angle_deg)
    if abs(tire) > motion_config['max_steering_angle_rad']:
        raise ValueError('Initial tire angle exceeds model limit')
    direction = np.array([math.cos(initial_heading), math.sin(initial_heading)])
    speed = float(velocity @ direction)
    yaw_rate = speed * math.tan(tire) / vehicle.wheel_base
    rear_accel = float(acceleration @ direction + vehicle.rear_axle_to_center * yaw_rate**2)
    rear_xy = points[0] - vehicle.rear_axle_to_center * direction
    state = EgoState.build_from_rear_axle(StateSE2(*rear_xy, initial_heading), StateVector2D(speed, 0.),
        StateVector2D(rear_accel, 0.), tire, TimePoint(0), vehicle, angular_vel=yaw_rate)
    states = [state]
    raw_commands, applied_commands, ticks = [], [], []
    for i in range(steps):
        is_tick = i % stride == 0
        if is_tick:
            tick = i // stride
            current = SimulationIteration(TimePoint(round(i * integration_dt * 1e6)), tick)
            following = SimulationIteration(TimePoint(round((i * integration_dt + control_dt) * 1e6)), tick + 1)
            command = tracker.track_trajectory(current, following, state, trajectory)
            raw = np.array([command.rear_axle_acceleration_2d.x, command.tire_steering_rate])
            applied = raw if mode == 'sdk_substep' else filtered_command(
                raw, state.dynamic_car_state.rear_axle_acceleration_2d.x, control_dt, motion_config)
        control = DynamicCarState.build_from_rear_axle(vehicle.rear_axle_to_center,
            state.dynamic_car_state.rear_axle_velocity_2d, StateVector2D(float(applied[0]), 0.),
            tire_steering_rate=float(applied[1]))
        raw_commands.append(raw.copy())
        applied_commands.append(applied.copy())
        ticks.append(is_tick)
        state = model.propagate_state(state, control, TimeDuration.from_s(integration_dt))
        states.append(state)
    times = np.arange(steps + 1) * integration_dt
    reference_times = np.arange(len(points)) * reference_dt
    centers = np.array([[s.center.x, s.center.y] for s in states])
    headings = np.array([s.center.heading for s in states])
    target = np.column_stack([np.interp(times, reference_times, points[:, k]) for k in (0, 1)])
    target_heading = np.interp(times, reference_times, np.unwrap(reference_heading))
    tire_angles = np.array([s.tire_steering_angle for s in states])
    speeds = np.array([s.dynamic_car_state.rear_axle_velocity_2d.x for s in states])
    accelerations = np.array([s.dynamic_car_state.rear_axle_acceleration_2d.x for s in states])
    arrays = dict(time_s=times, center_xy=centers, heading=headings, target_center_xy=target,
        target_heading=target_heading, tire_angle_rad=tire_angles, rear_speed_mps=speeds,
        rear_acceleration_mps2=accelerations, commands_accel_and_tire_rate=np.array(applied_commands),
        raw_commands_accel_and_tire_rate=np.array(raw_commands), control_tick=np.array(ticks, dtype=bool))
    if any(not np.isfinite(a).all() for a in arrays.values()):
        raise ValueError('Nonfinite controller result')
    error = np.linalg.norm(centers - target, axis=1)
    heading_error = np.arctan2(np.sin(headings - target_heading), np.cos(headings - target_heading))
    metrics = dict(rms_center_error_m=float(np.sqrt(np.mean(error**2))), maximum_center_error_m=float(error.max()),
        final_center_error_m=float(error[-1]), maximum_heading_error_deg=float(np.degrees(np.abs(heading_error)).max()),
        peak_abs_tire_angle_deg=float(np.degrees(np.abs(tire_angles)).max()),
        peak_abs_tire_rate_deg_per_s=float(np.degrees(np.abs(np.diff(tire_angles) / integration_dt)).max()),
        peak_abs_acceleration_mps2=float(np.abs(accelerations).max()), minimum_speed_mps=float(speeds.min()),
        reverse_speed_samples=int((speeds < -.001).sum()),
        model_steering_clamp_samples=int(np.isclose(np.abs(tire_angles), motion_config['max_steering_angle_rad'], atol=1e-8, rtol=0).sum()),
        initial_projected_rear_speed_mps=speed,
        observed_initial_center_lateral_speed_mps=float(velocity @ [-direction[1], direction[0]]),
        assumed_initial_center_lateral_speed_mps=float(vehicle.rear_axle_to_center * yaw_rate),
        control_updates=int(sum(ticks)), integration_steps=steps)
    return arrays, metrics
