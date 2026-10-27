"""Re-evaluate both policies from saved states, not just the motion model."""
import json
from functools import lru_cache
import numpy as np
from nuplan.common.actor_state.ego_state import EgoState
from nuplan.common.actor_state.state_representation import StateSE2,StateVector2D,TimePoint
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.simulation_time_controller.simulation_iteration import SimulationIteration
from evaluate_candidate_checks import load_graph,current_obstacles
from verify_tracking_diagnostic import verify_transitions
from mtr_project.controller_comparison import make_tracker,load_ilqr_config,initial_state,rollout_controller
from mtr_project.tracking_diagnostic import make_reference,load_lqr_config
from mtr_project.pose_geometry import check_poses
from mtr_project.paths import ROOT,sha256,write_json


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def verify_controls(data,row,spec,points,heading,lqr,ilqr):
    dt,cp=spec['integration_dt_seconds'],spec['control_dt_seconds'];stride=round(cp/dt)
    n=len(data['time_s']);vehicle=get_pacifica_parameters()
    tracker,solver=make_tracker(row['controller'],lqr,ilqr)
    trajectory,reference_heading=make_reference(points,heading,spec['reference_dt_seconds'])
    np.testing.assert_allclose(data['time_s'],np.arange(n)*dt,atol=1e-12,rtol=0)
    np.testing.assert_array_equal(data['control_tick'],np.arange(n-1)%stride==0)
    times=np.arange(len(points))*spec['reference_dt_seconds']
    target=np.column_stack([np.interp(data['time_s'],times,points[:,k]) for k in [0,1]])
    np.testing.assert_allclose(data['target_center_xy'],target,atol=1e-10,rtol=0)
    np.testing.assert_allclose(data['target_heading'],np.interp(data['time_s'],times,np.unwrap(reference_heading)),atol=1e-10,rtol=0)
    if row['status']=='completed' and len(row['diagnostics'])!=round(spec['simulation_duration_seconds']/cp):
        raise ValueError('Controller update diagnostics missing')
    largest=0.
    for i in range(0,n-1,stride):
        heading_i,tire,speed,accel=(float(data[k][i]) for k in ['heading','tire_angle_rad','rear_speed_mps','rear_acceleration_mps2'])
        rear=data['center_xy'][i]-vehicle.rear_axle_to_center*np.array([np.cos(heading_i),np.sin(heading_i)])
        state=EgoState.build_from_rear_axle(StateSE2(*rear,heading_i),StateVector2D(speed,0.),StateVector2D(accel,0.),
            tire,TimePoint(round(i*dt*1e6)),vehicle,angular_vel=speed*np.tan(tire)/vehicle.wheel_base)
        now=SimulationIteration(TimePoint(round(i*dt*1e6)),i//stride)
        following=SimulationIteration(TimePoint(round((i*dt+cp)*1e6)),i//stride+1)
        command=tracker.track_trajectory(now,following,state,trajectory)
        raw=np.array([command.rear_axle_acceleration_2d.x,command.tire_steering_rate])
        residual=float(np.max(np.abs(data['raw_commands_accel_and_tire_rate'][i:i+stride]-raw)))
        if residual>1e-7:raise ValueError('Scheduled controller command differs or was not held')
        largest=max(largest,residual)
        applied=np.array([accel+cp/(cp+spec['motion_model']['accel_time_constant_seconds'])*(raw[0]-accel),
                          cp/(cp+spec['motion_model']['steering_angle_time_constant_seconds'])*raw[1]])
        np.testing.assert_allclose(data['commands_accel_and_tire_rate'][i:i+stride],np.broadcast_to(applied,data['commands_accel_and_tire_rate'][i:i+stride].shape),atol=1e-7,rtol=0)
        diagnostic=row['diagnostics'][i//stride]
        if abs(diagnostic['time_s']-i*dt)>1e-10 or not np.isfinite(diagnostic['command_latency_seconds']) or diagnostic['command_latency_seconds']<0:
            raise ValueError('Invalid command diagnostic timing')
        if solver is not None:
            actual=solver.last_diagnostic
            for key in ['reference_states','iterations','solution_count']:
                if actual[key]!=diagnostic[key]:raise ValueError('Solver trace differs: '+key)
            if actual['reference_states']<3 or not 1<=actual['iterations']<=20:raise ValueError('Invalid solver boundary or iteration count')
            np.testing.assert_allclose(actual['costs'],diagnostic['costs'],atol=1e-7,rtol=1e-10)
            if np.any(np.asarray(diagnostic['costs'])<0):raise ValueError('Negative solver cost')
            if abs(raw[0])>ilqr['solver_params']['max_acceleration']+1e-8 or abs(raw[1])>ilqr['solver_params']['max_steering_angle_rate']+1e-8:
                raise ValueError('iLQR command outside configured limit')
    effective={**spec['motion_model'],'accel_time_constant_seconds':0.,'steering_angle_time_constant_seconds':0.}
    transition=verify_transitions(data,effective,dt)
    return largest,transition


def main():
    folder=ROOT/'runs/project-v2/controller-comparison-v1';path=folder/'experiment.json'
    experiment=json.loads(path.read_text());spec=experiment['specification'];plan_path=folder/'plan.json'
    if digest(plan_path)!=experiment['plan_sha256']:raise ValueError('Plan changed')
    plan=json.loads(plan_path.read_text())
    for field,value in plan.items():
        if experiment[field]!=value:raise ValueError('Experiment differs from plan')
    for mapping in [experiment['source_sha256'],experiment['implementation_sha256'],experiment['sdk_source_sha256']]:
        for name,expected in mapping.items():
            if digest(ROOT/name)!=expected:raise ValueError('Source changed: '+name)
    parent_path=ROOT/spec['source_population'];parent=json.loads(parent_path.read_text())
    parent_verified=json.loads(parent_path.with_name('verification.json').read_text())
    if parent_verified['experiment_sha256']!=digest(parent_path):raise ValueError('Unverified source population')
    if experiment['population']!=parent['population']:raise ValueError('Population was filtered or changed')
    expected={(p['key'],c,a) for p in parent['population'] for c in spec['controllers'] for a in spec['initial_tire_angles_deg']}
    actual={(r['proposal'],r['controller'],r['initial_tire_angle_deg']) for r in experiment['results']}
    if actual!=expected or len(actual)!=60 or len(experiment['results'])!=60:raise ValueError('Incomplete comparison')
    lqr=load_lqr_config(ROOT/spec['lqr_config']);ilqr=load_ilqr_config(ROOT/spec['ilqr_config'])
    if experiment['resolved_controller_configs']!={'lqr':lqr,'ilqr_iteration_limited':ilqr}:raise ValueError('Controller configuration changed')
    checked=[]
    for proposal in parent['population']:
        screen=json.loads((ROOT/proposal['screen']).read_text());conv=json.loads((ROOT/proposal['conversion']).read_text())
        center=np.load(ROOT/'runs'/proposal['window']['run']/'internal_0000.npz')['center']
        points=np.load(ROOT/proposal['reference_arrays'])['target_center_xy']
        graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);obstacles,bad=current_obstacles(conv)
        if bad:raise ValueError('Invalid current actors')
        for row in (r for r in experiment['results'] if r['proposal']==proposal['key']):
            if digest(ROOT/row['arrays'])!=row['arrays_sha256']:raise ValueError('Saved result changed')
            with np.load(ROOT/row['arrays'],allow_pickle=False) as saved:data={k:saved[k] for k in saved.files}
            n=len(data['time_s']);dt=spec['integration_dt_seconds']
            if row['status']=='completed':
                if row['failure'] is not None or n!=round(spec['simulation_duration_seconds']/dt)+1:raise ValueError('Completed trial is truncated')
            elif row['status']=='failed':
                _,_,_,failure=rollout_controller(points,float(center[6]),center[7:9],screen['summary']['initial_acceleration_from_past_only'],
                    row['initial_tire_angle_deg'],row['controller'],lqr,ilqr,spec['motion_model'],duration=spec['simulation_duration_seconds'],
                    control_dt=spec['control_dt_seconds'],integration_dt=dt,reference_dt=spec['reference_dt_seconds'])
                if failure!=row['failure']:raise ValueError('Recorded failure cannot be reproduced')
            else:raise ValueError('Unknown trial status')
            shapes={'time_s':(n,),'center_xy':(n,2),'heading':(n,),'target_center_xy':(n,2),'target_heading':(n,),
                'tire_angle_rad':(n,),'rear_speed_mps':(n,),'rear_acceleration_mps2':(n,),
                'commands_accel_and_tire_rate':(n-1,2),'raw_commands_accel_and_tire_rate':(n-1,2),'control_tick':(n-1,)}
            for key,shape in shapes.items():
                if data[key].shape!=shape or not np.isfinite(data[key]).all():raise ValueError('Invalid rollout array: '+key)
            initial=initial_state(points,float(center[6]),center[7:9],screen['summary']['initial_acceleration_from_past_only'],row['initial_tire_angle_deg'],spec['motion_model'])
            np.testing.assert_allclose(data['center_xy'][0],center[:2],atol=1e-9,rtol=0)
            np.testing.assert_allclose([data['heading'][0],data['tire_angle_rad'][0],data['rear_speed_mps'][0],data['rear_acceleration_mps2'][0]],
                [initial.center.heading,initial.tire_steering_angle,initial.dynamic_car_state.rear_axle_velocity_2d.x,initial.dynamic_car_state.rear_axle_acceleration_2d.x],atol=1e-10,rtol=0)
            command_residual,transition=verify_controls(data,row,spec,points,float(center[6]),lqr,ilqr)
            error=np.linalg.norm(data['center_xy']-data['target_center_xy'],axis=1);dh=data['heading']-data['target_heading'];angles=data['tire_angle_rad']
            recomputed=dict(maximum_center_error_m=float(error.max()),rms_center_error_m=float(np.sqrt(np.mean(error**2))),final_center_error_m=float(error[-1]),
                maximum_heading_error_deg=float(np.degrees(np.abs(np.arctan2(np.sin(dh),np.cos(dh)))).max()),
                peak_abs_tire_angle_deg=float(np.degrees(np.abs(angles)).max()),
                peak_abs_tire_rate_deg_per_s=float(np.degrees(np.abs(np.diff(angles)/dt)).max()) if n>1 else 0.,
                peak_abs_acceleration_mps2=float(np.abs(data['rear_acceleration_mps2']).max()),minimum_speed_mps=float(data['rear_speed_mps'].min()),
                reverse_speed_samples=int((data['rear_speed_mps']<-.001).sum()),
                model_steering_clamp_samples=int(np.isclose(np.abs(angles),spec['motion_model']['max_steering_angle_rad'],atol=1e-8,rtol=0).sum()),
                control_updates=int(data['control_tick'].sum()),integration_steps=n-1,completed_duration_seconds=float(data['time_s'][-1]))
            for key,value in recomputed.items():
                if not np.isclose(value,row['metrics'][key],atol=1e-10,rtol=0):raise ValueError('Metric differs: '+key)
            geometry=None if n<2 else check_poses(data['center_xy'],data['heading'],float(center[3]),float(center[4]),graph.surface,obstacles,dt=dt)
            if geometry!=row['simulated_pose_checks']:raise ValueError('Geometry check changed')
            checked.append({'key':row['key'],'controller_command_max_residual':command_residual,'motion_transition_max_residual':transition,
                            'completed':row['status']=='completed','geometry_recomputed':True})
        print('VERIFIED',proposal['key'],flush=True)
    result={'status':'passed_declared_controller_comparison_checks','experiment_sha256':sha256(path),'verifier_sha256':sha256(__file__),
        'trials_rechecked':len(checked),'checks':checked,'scope':'Both policies reevaluated at every saved control update; iLQR iteration/cost trace, held commands, initial observation, model transitions, common horizon and all body/CV checks rechecked. Latency is not reproducible timing evidence. Same SDK/model; not physical truth.'}
    write_json(folder/'verification.json',result);print(json.dumps({'status':result['status'],'trials_rechecked':len(checked)},indent=2))


if __name__=='__main__':main()
