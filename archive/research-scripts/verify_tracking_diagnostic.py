"""Reopen all fixed tracking rollouts and independently recheck stored transitions/geometry."""
import json
from functools import lru_cache
import numpy as np
from nuplan.common.actor_state.ego_state import EgoState
from nuplan.common.actor_state.dynamic_car_state import DynamicCarState
from nuplan.common.actor_state.state_representation import StateSE2,StateVector2D,TimePoint,TimeDuration
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.controller.motion_model.kinematic_bicycle import KinematicBicycleModel
from evaluate_candidate_checks import load_graph,current_obstacles
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.corridor_reserve import target_reserve,margin_key
from mtr_project.pose_geometry import check_poses
from mtr_project.paths import ROOT,sha256,write_json


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def verify_transitions(data,motion,dt):
    vehicle=get_pacifica_parameters();model=KinematicBicycleModel(vehicle,motion['max_steering_angle_rad'],motion['accel_time_constant_seconds'],motion['steering_angle_time_constant_seconds'])
    largest=0.
    for i,command in enumerate(data['commands_accel_and_tire_rate']):
        h=float(data['heading'][i]);tire=float(data['tire_angle_rad'][i]);speed=float(data['rear_speed_mps'][i]);accel=float(data['rear_acceleration_mps2'][i])
        rear=data['center_xy'][i]-vehicle.rear_axle_to_center*np.array([np.cos(h),np.sin(h)])
        state=EgoState.build_from_rear_axle(StateSE2(*rear,h),StateVector2D(speed,0.),StateVector2D(accel,0.),tire,
                    TimePoint(round(i*dt*1e6)),vehicle,angular_vel=speed*np.tan(tire)/vehicle.wheel_base)
        control=DynamicCarState.build_from_rear_axle(vehicle.rear_axle_to_center,StateVector2D(speed,0.),StateVector2D(float(command[0]),0.),tire_steering_rate=float(command[1]))
        next_state=model.propagate_state(state,control,TimeDuration.from_s(dt))
        expected=np.array([next_state.center.x,next_state.center.y,next_state.center.heading,next_state.tire_steering_angle,next_state.dynamic_car_state.rear_axle_velocity_2d.x,next_state.dynamic_car_state.rear_axle_acceleration_2d.x])
        actual=np.r_[data['center_xy'][i+1],data['heading'][i+1],data['tire_angle_rad'][i+1],data['rear_speed_mps'][i+1],data['rear_acceleration_mps2'][i+1]]
        residual=float(np.max(np.abs(expected-actual)));largest=max(largest,residual)
        if residual>1e-8:raise ValueError('Stored state does not follow logged command and official motion model')
    return largest


def main():
    folder=ROOT/'runs/project-v2/tracking-diagnostic-v1';path=folder/'experiment.json';experiment=json.loads(path.read_text());spec=experiment['specification']
    parent=json.loads((ROOT/spec['source_experiment']).read_text())
    for mapping in [experiment['source_sha256'],experiment['implementation_sha256'],experiment['sdk_source_sha256'],parent['source_sha256'],parent['implementation_sha256']]:
        for name,expected in mapping.items():
            if digest(ROOT/name)!=expected:raise ValueError('Input/implementation changed: '+name)
    # The parent source map includes exact DB hashes used for present actors;
    # check this transitively, since the child receipt stores the parent hash.
    expected={(w['key'],r['candidate'],dt,tire) for w in parent['windows'] for r in w['accepted'] for dt in spec['integration_dt_seconds'] for tire in spec['initial_tire_angles_deg']}
    actual={(r['window'],r['candidate'],r['simulation_dt'],r['initial_tire_angle_deg']) for r in experiment['results']}
    if len(expected)!=54 or actual!=expected or len(experiment['results'])!=54:raise ValueError('Incomplete or duplicate fixed population')
    checked=[]
    for window in parent['windows']:
        if not window['accepted']:continue
        source=ROOT/'runs'/window['run'];screen=json.loads((source/'anchored_feasibility.json').read_text())
        conv=json.loads((ROOT/'samples'/screen['summary']['sample']/'conversion.json').read_text())
        raw=np.load(source/'internal_0000.npz');center=raw['center']
        graph,_=add_parallel_connector_edges(load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']))
        obstacles,bad=current_obstacles(conv)
        if bad:raise ValueError('Invalid current obstacles')
        print('RECHECK TRACKING',window['key'],flush=True)
        for row in (r for r in experiment['results'] if r['window']==window['key']):
            output=ROOT/row['arrays'];dt=row['simulation_dt']
            if digest(output)!=row['arrays_sha256']:raise ValueError('Saved rollout changed')
            with np.load(output,allow_pickle=False) as saved:data={k:saved[k] for k in saved.files}
            n=round(6/dt)+1
            if data['center_xy'].shape!=(n,2) or data['commands_accel_and_tire_rate'].shape!=(n-1,2):raise ValueError('Unexpected rollout shape')
            if any(not np.isfinite(a).all() for a in data.values()):raise ValueError('Nonfinite rollout')
            np.testing.assert_allclose(data['time_s'],np.arange(n)*dt,rtol=0,atol=1e-12)
            np.testing.assert_allclose(data['center_xy'][0],center[:2],rtol=0,atol=1e-9)
            error=np.linalg.norm(data['center_xy']-data['target_center_xy'],axis=1)
            for name,value in [('maximum_center_error_m',error.max()),('rms_center_error_m',np.sqrt(np.mean(error**2))),('final_center_error_m',error[-1]),
                               ('peak_abs_tire_angle_deg',np.degrees(np.abs(data['tire_angle_rad'])).max()),('peak_abs_acceleration_mps2',np.abs(data['rear_acceleration_mps2']).max())]:
                if not np.isclose(value,row['metrics'][name],atol=1e-10,rtol=0):raise ValueError('Stored summary differs from arrays')
            transition_residual=verify_transitions(data,spec['motion_model'],dt)
            geometry=check_poses(data['center_xy'],data['heading'],float(center[3]),float(center[4]),graph.surface,obstacles,dt=dt)
            if geometry!=row['simulated_pose_checks']:raise ValueError('Simulated body/CV check differs')
            route=screen['candidates'][row['candidate']-1]['route'];event=route['lane_changes'][0]
            target=graph.forward_corridor(event['to'])
            reserve=target_reserve(data['center_xy'],[data['heading']],float(center[3]),float(center[4]),target,0.,[spec['target_corridor_reserve_m']],dt=dt)
            if reserve[margin_key(spec['target_corridor_reserve_m'])]!=row['final_half_second_target_reserve']:raise ValueError('Target reserve check differs')
            checked.append({'key':row['key'],'maximum_motion_transition_residual':transition_residual,'geometry_recomputed':True})
    result={'status':'passed_declared_tracking_evidence_checks','experiment_sha256':sha256(path),'verifier_sha256':sha256(__file__),
            'rollouts_rechecked':len(checked),'checked':checked,'parent_source_hashes_rechecked':True,
            'scope':'Reopened all54 arrays; checked full Cartesian coverage, parent DB/map/source hashes, logged-command motion transitions, errors and geometry. Same official motion/checker implementations; not independent physical truth or full benchmark.'}
    write_json(folder/'verification.json',result);print(json.dumps({'status':result['status'],'rollouts_rechecked':len(checked),'max_transition_residual':max(r['maximum_motion_transition_residual'] for r in checked)},indent=2))


if __name__=='__main__':main()
