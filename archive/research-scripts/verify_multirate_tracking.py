"""Check timing, held commands, controller calls, model transitions and geometry."""
import json
from functools import lru_cache
import numpy as np
from nuplan.common.actor_state.ego_state import EgoState
from nuplan.common.actor_state.state_representation import StateSE2, StateVector2D, TimePoint
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.controller.tracker.lqr import LQRTracker
from nuplan.planning.simulation.simulation_time_controller.simulation_iteration import SimulationIteration
from evaluate_candidate_checks import load_graph, current_obstacles
from verify_tracking_diagnostic import verify_transitions
from mtr_project.tracking_diagnostic import make_reference, load_lqr_config
from mtr_project.pose_geometry import check_poses
from mtr_project.paths import ROOT, sha256, write_json


@lru_cache(maxsize=None)
def digest(path): return sha256(path)


def evidence_path(parent_path, name):
    """Resolve the two historical sequence schemas explicitly; never skip a hash."""
    if parent_path.name.startswith('sequence-report') and parent_path.parent.name in ('annotation-sequence-v1','second-annotation-v1'):
        replay = ('doplan_006160-window-v2-corridor-v1.json' if parent_path.parent.name=='annotation-sequence-v1'
                  else 'doplan_000567-camera-window-v1-corridor-v1.json')
        aliases = {'manifest':parent_path.parent/'sequence-manifest.json',
                   'configuration':parent_path.parent/'sequence-config.json',
                   'observations':ROOT/'runs/project-v2/replay'/replay,
                   'planner':ROOT/'scripts/mtr_project/planner.py',
                   'evaluator':ROOT/'scripts/evaluate_annotation_sequence.py'}
        if name in aliases: return aliases[name]
        if name in ('mtr_project/stages.py','mtr_project/language.py','language_selector.py'):
            return ROOT/'scripts'/name
    return ROOT/name


def verify_schedule(data, control_dt, dt, mode, motion, points, heading, controller):
    n = round(6. / dt) + 1 if len(points) == 121 else round((len(points) - 1) * .05 / dt) + 1
    stride = round(control_dt / dt)
    shapes = {'time_s':(n,), 'center_xy':(n,2), 'heading':(n,), 'target_center_xy':(n,2),
        'target_heading':(n,), 'tire_angle_rad':(n,), 'rear_speed_mps':(n,), 'rear_acceleration_mps2':(n,),
        'commands_accel_and_tire_rate':(n-1,2), 'raw_commands_accel_and_tire_rate':(n-1,2), 'control_tick':(n-1,)}
    if mode not in ('sdk_substep', 'control_period_filter') or stride < 1 or (n-1) % stride:
        raise ValueError('Unknown schedule')
    for key, shape in shapes.items():
        if data[key].shape != shape or not np.isfinite(data[key]).all(): raise ValueError('Bad saved array: ' + key)
    np.testing.assert_allclose(data['time_s'], np.arange(n) * dt, atol=1e-12, rtol=0)
    np.testing.assert_array_equal(data['control_tick'], np.arange(n-1) % stride == 0)
    vehicle = get_pacifica_parameters()
    reference, headings = make_reference(points, heading, .05)
    times = np.arange(len(points)) * .05
    expected_target = np.column_stack([np.interp(data['time_s'], times, points[:, k]) for k in [0,1]])
    np.testing.assert_allclose(data['target_center_xy'], expected_target, atol=1e-10, rtol=0)
    np.testing.assert_allclose(data['target_heading'], np.interp(data['time_s'], times, np.unwrap(headings)), atol=1e-10, rtol=0)
    tracker = LQRTracker(**controller, vehicle=vehicle)
    largest = 0.
    for i in range(0, n-1, stride):
        h, tire, speed, accel = (float(data[name][i]) for name in ['heading', 'tire_angle_rad', 'rear_speed_mps', 'rear_acceleration_mps2'])
        rear = data['center_xy'][i] - vehicle.rear_axle_to_center * np.array([np.cos(h), np.sin(h)])
        state = EgoState.build_from_rear_axle(StateSE2(*rear,h), StateVector2D(speed,0.), StateVector2D(accel,0.), tire,
            TimePoint(round(i * dt * 1e6)), vehicle, angular_vel=speed * np.tan(tire) / vehicle.wheel_base)
        current = SimulationIteration(TimePoint(round(i * dt * 1e6)), i // stride)
        following = SimulationIteration(TimePoint(round((i * dt + control_dt) * 1e6)), i // stride + 1)
        control = tracker.track_trajectory(current, following, state, reference)
        raw = np.array([control.rear_axle_acceleration_2d.x, control.tire_steering_rate])
        block = data['raw_commands_accel_and_tire_rate'][i:i+stride]
        residual = float(np.max(np.abs(block - raw)))
        largest = max(largest, residual)
        if residual > 1e-8: raise ValueError('Stored command differs from scheduled feedback or is not held')
        expected = raw.copy()
        if mode == 'control_period_filter':
            expected[0] = accel + control_dt / (control_dt + motion['accel_time_constant_seconds']) * (raw[0] - accel)
            expected[1] = raw[1] * control_dt / (control_dt + motion['steering_angle_time_constant_seconds'])
        if np.max(np.abs(data['commands_accel_and_tire_rate'][i:i+stride] - expected)) > 1e-8:
            raise ValueError('Actuator command differs from declared schedule')
    effective = dict(motion)
    if mode == 'control_period_filter':
        effective['accel_time_constant_seconds'] = 0.
        effective['steering_angle_time_constant_seconds'] = 0.
    return largest, verify_transitions(data, effective, dt)


def main():
    folder = ROOT / 'runs/project-v2/multirate-tracking-v1'
    path = folder / 'experiment.json'
    experiment = json.loads(path.read_text())
    spec = experiment['specification']
    plan_path = folder / 'plan.json'
    if digest(plan_path) != experiment['plan_sha256']: raise ValueError('Plan changed')
    plan = json.loads(plan_path.read_text())
    for field in plan:
        if plan[field] != experiment[field]: raise ValueError('Experiment differs from preregistered plan')
    pending = [(path,experiment)]
    seen = set()
    historical_sources = []
    while pending:
        parent_path,item = pending.pop()
        for field in ('source_sha256','implementation_sha256','sdk_source_sha256'):
            for name, expected in item.get(field, {}).items():
                source = evidence_path(parent_path,name)
                if digest(source) != expected:
                    historical = parent_path.name.startswith('sequence-report') and parent_path.parent.name in ('annotation-sequence-v1','second-annotation-v1')
                    if historical and source.is_relative_to(ROOT/'scripts'):
                        relative = source.relative_to(ROOT)
                        matches = [p/relative for p in sorted((ROOT/'runs/project-v2/source-backups').iterdir())
                                   if (p/relative).is_file() and digest(p/relative)==expected]
                        if not matches: raise ValueError('Historical source snapshot missing: ' + name)
                        historical_sources.append({'receipt':str(parent_path.relative_to(ROOT)), 'current_file':str(relative),
                            'historical_snapshot':str(matches[0].relative_to(ROOT)), 'expected_sha256':expected})
                        source = matches[0]
                    else: raise ValueError('Evidence changed: ' + name)
                # Follow JSON evidence receipts to DB/map inputs, not just the parent receipt's own bytes.
                if source.suffix == '.json' and source not in seen:
                    seen.add(source)
                    value = json.loads(source.read_text())
                    if isinstance(value,dict): pending.append((source,value))
    expected_proposals = set()
    for name in spec['parent_experiments']:
        parent = json.loads((ROOT / name).read_text())
        for r in parent['results']:
            if r['simulation_dt'] == .05 and r['initial_tire_angle_deg'] == 0.:
                w = r['window'] if isinstance(r['window'],str) else r['window']['key']
                expected_proposals.add(w + f'--q{r["candidate"]:02d}')
    population = experiment['population']
    if len(population) != 10 or {p['key'] for p in population} != expected_proposals:
        raise ValueError('Incomplete proposal population')
    expected = {(p, s['control_dt'], s['integration_dt'], m) for p in expected_proposals for s in spec['schedule'] for m in spec['modes']}
    actual = {(r['proposal'],r['control_dt'],r['integration_dt'],r['mode']) for r in experiment['results']}
    if actual != expected or len(actual) != 100 or len(experiment['results']) != 100: raise ValueError('Grid incomplete or duplicated')
    controller = load_lqr_config(ROOT / spec['tracker_config'])
    checked = []
    for p in population:
        conv = json.loads((ROOT / p['conversion']).read_text())
        center = np.load(ROOT / 'runs' / p['window']['run'] / 'internal_0000.npz')['center']
        points = np.load(ROOT / p['reference_arrays'])['target_center_xy']
        graph = load_graph(np.asarray(conv['origin_xy_m']), conv['source_epsg'], conv['source_map'])
        obstacles, bad = current_obstacles(conv)
        if bad: raise ValueError('Invalid current actors')
        for row in (r for r in experiment['results'] if r['proposal'] == p['key']):
            if digest(ROOT / row['arrays']) != row['arrays_sha256']: raise ValueError('Rollout changed')
            with np.load(ROOT / row['arrays'], allow_pickle=False) as saved: data = {k:saved[k] for k in saved.files}
            dt, cp = row['integration_dt'], row['control_dt']
            np.testing.assert_allclose(data['center_xy'][0], center[:2], atol=1e-9, rtol=0)
            if row['initial_tire_angle_deg'] != 0. or abs(data['tire_angle_rad'][0]) > 1e-12: raise ValueError('Initial tire changed')
            command_residual, transition_residual = verify_schedule(data, cp, dt, row['mode'], spec['motion_model'], points, float(center[6]), controller)
            error = np.linalg.norm(data['center_xy'] - data['target_center_xy'], axis=1)
            for name, value in [('maximum_center_error_m',error.max()),('rms_center_error_m',np.sqrt(np.mean(error**2))),('final_center_error_m',error[-1]),
                                ('control_updates',len(np.flatnonzero(data['control_tick']))),('integration_steps',len(error)-1)]:
                if not np.isclose(row['metrics'][name],value,atol=1e-10,rtol=0): raise ValueError('Metric differs from arrays')
            stride = round(.1 / dt)
            if not np.isclose(error[::stride].max(),row['common_sample_max_error_m'],atol=1e-10,rtol=0): raise ValueError('Common-sample error mismatch')
            for label, hop, interval in [('dense_pose_checks',1,dt),('common_pose_checks',stride,.1)]:
                geometry = check_poses(data['center_xy'][::hop],data['heading'][::hop],float(center[3]),float(center[4]),graph.surface,obstacles,dt=interval)
                if geometry != row[label]: raise ValueError('Pose checks changed')
            equal_residual = None
            if cp == dt:
                old = np.load(ROOT / p['nominal_baselines'][str(cp)]['arrays'])
                equal_residual = max(float(np.max(np.abs((data['raw_commands_accel_and_tire_rate'] if k == 'commands_accel_and_tire_rate' else data[k]) - old[k]))) for k in old.files)
                if equal_residual > 1e-8 or not np.isclose(equal_residual,row['equal_rate_max_residual'],atol=1e-12,rtol=0): raise ValueError('Old result not reproduced')
            elif row['equal_rate_max_residual'] is not None: raise ValueError('Unequal schedule claims exact old comparison')
            checked.append(dict(key=row['key'], maximum_controller_command_residual=command_residual,
                maximum_motion_transition_residual=transition_residual, equal_rate_max_residual=equal_residual))
        print('VERIFIED',p['key'],flush=True)
    result = dict(status='passed_declared_multirate_checks', experiment_sha256=sha256(path), verifier_sha256=sha256(__file__),
        rollout_count=len(checked), checks=checked, historical_source_snapshots=historical_sources,
        scope='All scheduled LQR calls independently reevaluated from stored states, held actuator commands checked, every model transition and common/dense geometry recomputed. Historical sequence generator hashes may refer to explicitly listed archived versions, not the current generator. Same SDK/model/checker; not physical truth.')
    write_json(folder / 'verification.json', result)
    print(json.dumps({'status':result['status'],'rollouts':len(checked),'old_equal_rate_matches':sum(r['equal_rate_max_residual'] is not None for r in checked)},indent=2))


if __name__ == '__main__': main()
