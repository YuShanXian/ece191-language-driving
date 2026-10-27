"""Matched frozen-reference controller comparison with an explicit terminal boundary."""
import math
import time
from dataclasses import asdict
import numpy as np
import yaml
from nuplan.common.actor_state.dynamic_car_state import DynamicCarState
from nuplan.common.actor_state.ego_state import EgoState
from nuplan.common.actor_state.state_representation import StateSE2, StateVector2D, TimePoint, TimeDuration
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.controller.tracker.lqr import LQRTracker
from nuplan.planning.simulation.controller.tracker.ilqr_tracker import ILQRTracker
from nuplan.planning.simulation.controller.tracker.ilqr.ilqr_solver import ILQRSolver, ILQRSolverParameters, ILQRWarmStartParameters
from nuplan.planning.simulation.controller.motion_model.kinematic_bicycle import KinematicBicycleModel
from nuplan.planning.simulation.simulation_time_controller.simulation_iteration import SimulationIteration
from .tracking_diagnostic import make_reference, load_lqr_config
from .multirate_tracking import timing_grid, filtered_command


class AuditedSolver(ILQRSolver):
    """Observe returned SDK solutions; do not choose a different iterate or alter optimization."""
    def solve(self, current_state, reference_trajectory):
        solutions = super().solve(current_state, reference_trajectory)
        self.last_diagnostic = dict(reference_states=len(reference_trajectory), iterations=len(solutions)-1,
            solution_count=len(solutions), costs=[float(s.tracking_cost) for s in solutions])
        return solutions


def load_ilqr_config(path):
    source = yaml.safe_load(path.read_text())
    def typed(mapping):
        values = {}
        for key, value in mapping.items():
            if key.startswith('_'): continue
            values[key] = ([float(x) for x in value] if isinstance(value,list) else
                           int(value) if key == 'max_ilqr_iterations' else float(value))
        return values
    solver = typed(source['ilqr_solver']['solver_params'])
    solver['max_solve_time'] = None  # Sole declared override; iteration bound/convergence preserved.
    warm = typed(source['ilqr_solver']['warm_start_params'])
    return dict(n_horizon=int(source['n_horizon']), solver_params=solver, warm_start_params=warm)


def make_tracker(name, lqr_config, ilqr_config):
    vehicle = get_pacifica_parameters()
    if name == 'lqr': return LQRTracker(**lqr_config, vehicle=vehicle), None
    if name != 'ilqr_iteration_limited': raise ValueError('Unsupported controller')
    solver = AuditedSolver(ILQRSolverParameters(**ilqr_config['solver_params']),
                           ILQRWarmStartParameters(**ilqr_config['warm_start_params']))
    return ILQRTracker(ilqr_config['n_horizon'], solver), solver


def initial_state(points, heading, velocity, acceleration, tire_deg, motion):
    vehicle = get_pacifica_parameters()
    velocity, acceleration = np.asarray(velocity,float), np.asarray(acceleration,float)
    if velocity.shape!=(2,) or acceleration.shape!=(2,) or not np.isfinite(np.r_[velocity,acceleration,heading,tire_deg]).all():
        raise ValueError('Invalid initial dynamics')
    tire = math.radians(tire_deg)
    if abs(tire)>motion['max_steering_angle_rad']: raise ValueError('Initial tire angle outside model range')
    direction = np.array([math.cos(heading),math.sin(heading)])
    speed = float(velocity @ direction)
    yaw = speed * math.tan(tire) / vehicle.wheel_base
    rear_accel = float(acceleration @ direction + vehicle.rear_axle_to_center * yaw**2)
    rear = points[0] - vehicle.rear_axle_to_center * direction
    return EgoState.build_from_rear_axle(StateSE2(*rear,heading),StateVector2D(speed,0.),StateVector2D(rear_accel,0.),
        tire,TimePoint(0),vehicle,angular_vel=yaw)


def validate_horizon(points, reference_dt, duration, control_dt, integration_dt, ilqr_dt):
    steps,stride=timing_grid(duration,control_dt,integration_dt)
    reference_horizon=(len(points)-1)*reference_dt
    if duration>reference_horizon+1e-9 or duration-control_dt+2*ilqr_dt>reference_horizon+1e-9:
        raise ValueError('Last control update must retain at least three original iLQR reference states')
    return steps,stride


def rollout_controller(points, heading, velocity, acceleration, tire_deg, name, lqr_config, ilqr_config, motion,
                       duration=5.8, control_dt=.2, integration_dt=.05, reference_dt=.05):
    points=np.asarray(points,float)
    steps,stride=validate_horizon(points,reference_dt,duration,control_dt,integration_dt,
                                  ilqr_config['solver_params']['discretization_time'])
    reference,reference_heading=make_reference(points,heading,reference_dt)
    tracker,solver=make_tracker(name,lqr_config,ilqr_config)
    state=initial_state(points,heading,velocity,acceleration,tire_deg,motion)
    vehicle=get_pacifica_parameters()
    model=KinematicBicycleModel(vehicle,motion['max_steering_angle_rad'],0.,0.)
    states=[state];raw_commands=[];applied_commands=[];ticks=[];diagnostics=[];failure=None
    for i in range(steps):
        try:
            tick=i%stride==0
            if tick:
                now=SimulationIteration(TimePoint(round(i*integration_dt*1e6)),i//stride)
                next_time=SimulationIteration(TimePoint(round((i*integration_dt+control_dt)*1e6)),i//stride+1)
                started=time.perf_counter()
                command=tracker.track_trajectory(now,next_time,state,reference)
                elapsed=time.perf_counter()-started
                raw=np.array([command.rear_axle_acceleration_2d.x,command.tire_steering_rate])
                if not np.isfinite(raw).all(): raise ValueError('Nonfinite controller command')
                applied=filtered_command(raw,state.dynamic_car_state.rear_axle_acceleration_2d.x,control_dt,motion)
                diagnostic=dict(time_s=i*integration_dt,command_latency_seconds=elapsed)
                if solver is not None: diagnostic.update(solver.last_diagnostic)
                diagnostics.append(diagnostic)
            control=DynamicCarState.build_from_rear_axle(vehicle.rear_axle_to_center,state.dynamic_car_state.rear_axle_velocity_2d,
                StateVector2D(float(applied[0]),0.),tire_steering_rate=float(applied[1]))
            following=model.propagate_state(state,control,TimeDuration.from_s(integration_dt))
            if not np.isfinite([following.center.x,following.center.y,following.center.heading,following.tire_steering_angle,
                                following.dynamic_car_state.rear_axle_velocity_2d.x,following.dynamic_car_state.rear_axle_acceleration_2d.x]).all():
                raise ValueError('Nonfinite propagated state')
            raw_commands.append(raw.copy());applied_commands.append(applied.copy());ticks.append(tick)
            state=following;states.append(state)
        except (AssertionError,IndexError,ValueError,RuntimeError,ArithmeticError) as error:
            failure=dict(time_s=i*integration_dt,exception_type=type(error).__name__,message=str(error))
            break  # Retain the failed trial and prefix; never silently switch controller.
    times=np.arange(len(states))*integration_dt
    reference_times=np.arange(len(points))*reference_dt
    target=np.column_stack([np.interp(times,reference_times,points[:,k]) for k in [0,1]])
    target_heading=np.interp(times,reference_times,np.unwrap(reference_heading))
    arrays=dict(time_s=times,center_xy=np.array([[s.center.x,s.center.y] for s in states]),heading=np.array([s.center.heading for s in states]),
        target_center_xy=target,target_heading=target_heading,tire_angle_rad=np.array([s.tire_steering_angle for s in states]),
        rear_speed_mps=np.array([s.dynamic_car_state.rear_axle_velocity_2d.x for s in states]),
        rear_acceleration_mps2=np.array([s.dynamic_car_state.rear_axle_acceleration_2d.x for s in states]),
        commands_accel_and_tire_rate=np.asarray(applied_commands).reshape(-1,2),
        raw_commands_accel_and_tire_rate=np.asarray(raw_commands).reshape(-1,2),control_tick=np.asarray(ticks,dtype=bool))
    metrics=summarize_arrays(arrays,motion,integration_dt)
    metrics['completed_duration_seconds']=float(times[-1])
    return arrays,metrics,diagnostics,failure


def summarize_arrays(arrays,motion,dt):
    error=np.linalg.norm(arrays['center_xy']-arrays['target_center_xy'],axis=1)
    dh=arrays['heading']-arrays['target_heading']
    angles=arrays['tire_angle_rad'];speeds=arrays['rear_speed_mps']
    return dict(maximum_center_error_m=float(error.max()),rms_center_error_m=float(np.sqrt(np.mean(error**2))),
        final_center_error_m=float(error[-1]),maximum_heading_error_deg=float(np.degrees(np.abs(np.arctan2(np.sin(dh),np.cos(dh)))).max()),
        peak_abs_tire_angle_deg=float(np.degrees(np.abs(angles)).max()),
        peak_abs_tire_rate_deg_per_s=float(np.degrees(np.abs(np.diff(angles)/dt)).max()) if len(angles)>1 else 0.,
        peak_abs_acceleration_mps2=float(np.abs(arrays['rear_acceleration_mps2']).max()),minimum_speed_mps=float(speeds.min()),
        reverse_speed_samples=int((speeds<-.001).sum()),
        model_steering_clamp_samples=int(np.isclose(np.abs(angles),motion['max_steering_angle_rad'],atol=1e-8,rtol=0).sum()),
        control_updates=int(arrays['control_tick'].sum()),integration_steps=len(error)-1)
