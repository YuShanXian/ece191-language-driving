"""Run the declared timing grid over every prior nominal merge/turn proposal."""
import inspect
import json
import numpy as np
from nuplan.common.actor_state.ego_state import EgoState
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.controller.tracker.lqr import LQRTracker
from nuplan.planning.simulation.controller.tracker import tracker_utils
from nuplan.planning.simulation.controller.motion_model.kinematic_bicycle import KinematicBicycleModel
from nuplan.planning.simulation.trajectory.interpolated_trajectory import InterpolatedTrajectory
from evaluate_candidate_checks import load_graph, current_obstacles
from mtr_project.multirate_tracking import track_multirate_path
from mtr_project.pose_geometry import check_poses
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.paths import ROOT, sha256, write_json


def check_hashes(document):
    for field in ('source_sha256', 'implementation_sha256', 'sdk_source_sha256'):
        for name, expected in document.get(field, {}).items():
            if sha256(ROOT / name) != expected:
                raise ValueError('Parent/input changed: ' + name)


def load_population(spec):
    population, sources = [], {}
    for name in spec['parent_experiments']:
        path = ROOT / name
        parent = json.loads(path.read_text())
        verification_path = path.with_name('verification.json')
        verification = json.loads(verification_path.read_text())
        if verification['experiment_sha256'] != sha256(path):
            raise ValueError('Unverified tracking parent')
        check_hashes(parent)
        sources[name] = sha256(path)
        sources[str(verification_path.relative_to(ROOT))] = sha256(verification_path)
        if 'source_experiment' in parent['specification']:
            upstream_path = ROOT / parent['specification']['source_experiment']
            upstream = json.loads(upstream_path.read_text())
            check_hashes(upstream)
            windows = {w['key']: w for w in upstream['windows']}
        else:
            upstream_path = ROOT / parent['specification']['source_evaluation']
            check_hashes(json.loads(upstream_path.read_text()))
            windows = None
        sources[str(upstream_path.relative_to(ROOT))] = sha256(upstream_path)
        for row in parent['results']:
            if row['initial_tire_angle_deg'] != 0. or row['simulation_dt'] != .05:
                continue
            window = windows[row['window']] if windows is not None else row['window']
            key = window['key'] + f'--q{row["candidate"]:02d}'
            old = {str(dt): next(r for r in parent['results'] if r['window'] == row['window'] and
                   r['candidate'] == row['candidate'] and r['initial_tire_angle_deg'] == 0. and r['simulation_dt'] == dt)
                   for dt in (.1, .05)}
            for baseline in old.values():
                if sha256(ROOT / baseline['arrays']) != baseline['arrays_sha256']:
                    raise ValueError('Prior nominal rollout changed')
                sources[baseline['arrays']] = baseline['arrays_sha256']
            folder = ROOT / 'runs' / window['run']
            screen_path = folder / 'anchored_feasibility.json'
            screen = json.loads(screen_path.read_text())
            conversion_path = ROOT / 'samples' / screen['summary']['sample'] / 'conversion.json'
            conv = json.loads(conversion_path.read_text())
            for source in [screen_path, conversion_path, folder / 'internal_0000.npz',
                           ROOT / conv['source_db'], ROOT / conv['source_map']]:
                relative = str(source.relative_to(ROOT))
                if relative not in sources:
                    sources[relative] = sha256(source)
            population.append(dict(key=key, window=window, candidate=row['candidate'], action=row['action'],
                parent_experiment=name, nominal_baselines=old, reference_arrays=row['arrays'],
                screen=str(screen_path.relative_to(ROOT)), conversion=str(conversion_path.relative_to(ROOT))))
    if len(population) != spec['expected_unique_proposals'] or len({p['key'] for p in population}) != len(population):
        raise ValueError('Population differs from preregistration')
    return population, sources


def main():
    spec_path = ROOT / 'config/multirate-tracking-v1.json'
    spec = json.loads(spec_path.read_text())
    folder = ROOT / 'runs/project-v2' / spec['output_tag']
    if folder.exists():
        raise FileExistsError('Preserve prior timing experiment')
    population, sources = load_population(spec)
    sources[str(spec_path.relative_to(ROOT))] = sha256(spec_path)
    sources[spec['tracker_config']] = sha256(ROOT / spec['tracker_config'])
    code = ['scripts/run_multirate_tracking.py', 'scripts/mtr_project/multirate_tracking.py',
            'scripts/mtr_project/tracking_diagnostic.py', 'scripts/mtr_project/kinematic_diagnostic.py',
            'scripts/mtr_project/pose_geometry.py', 'scripts/evaluate_candidate_checks.py', 'scripts/trajectory_checks.py']
    implementation = {name: sha256(ROOT / name) for name in code}
    sdk = {inspect.getfile(item): sha256(inspect.getfile(item)) for item in
           [LQRTracker, tracker_utils, KinematicBicycleModel, EgoState, InterpolatedTrajectory, get_pacifica_parameters]}
    plan = dict(specification=spec, population=population, source_sha256=sources,
                implementation_sha256=implementation, sdk_source_sha256=sdk)
    folder.mkdir()
    write_json(folder / 'plan.json', plan)
    controller = load_lqr_config(ROOT / spec['tracker_config'])
    results = []
    for proposal in population:
        screen = json.loads((ROOT / proposal['screen']).read_text())
        conv = json.loads((ROOT / proposal['conversion']).read_text())
        center = np.load(ROOT / 'runs' / proposal['window']['run'] / 'internal_0000.npz')['center']
        points = np.load(ROOT / proposal['reference_arrays'])['target_center_xy']
        graph = load_graph(np.asarray(conv['origin_xy_m']), conv['source_epsg'], conv['source_map'])
        obstacles, bad = current_obstacles(conv)
        if bad: raise ValueError('Invalid current actors')
        for schedule in spec['schedule']:
            for mode in spec['modes']:
                cp, dt = schedule['control_dt'], schedule['integration_dt']
                arrays, metrics = track_multirate_path(points, float(center[6]), center[7:9],
                    screen['summary']['initial_acceleration_from_past_only'], 0., controller, spec['motion_model'],
                    control_dt=cp, integration_dt=dt, mode=mode)
                dense = check_poses(arrays['center_xy'], arrays['heading'], float(center[3]), float(center[4]), graph.surface, obstacles, dt=dt)
                stride = round(.1 / dt)
                common = check_poses(arrays['center_xy'][::stride], arrays['heading'][::stride], float(center[3]), float(center[4]), graph.surface, obstacles, dt=.1)
                common_error = np.linalg.norm(arrays['center_xy'][::stride] - arrays['target_center_xy'][::stride], axis=1)
                match = None
                if cp == dt:
                    old = np.load(ROOT / proposal['nominal_baselines'][str(cp)]['arrays'])
                    differences = []
                    for field in old.files:
                        actual = arrays['raw_commands_accel_and_tire_rate'] if field == 'commands_accel_and_tire_rate' else arrays[field]
                        residual = float(np.max(np.abs(actual - old[field])))
                        if residual > 1e-8: raise ValueError('Equal-rate rollout did not reproduce old evidence')
                        differences.append(residual)
                    match = max(differences)
                key = proposal['key'] + f'--cp{cp:.3f}--dt{dt:.3f}--{mode}'
                output = folder / (key + '.npz')
                np.savez_compressed(output, **arrays)
                results.append(dict(key=key, proposal=proposal['key'], control_dt=cp, integration_dt=dt, mode=mode,
                    initial_tire_angle_deg=0., metrics=metrics, common_sample_max_error_m=float(common_error.max()),
                    common_pose_checks=common, dense_pose_checks=dense, equal_rate_max_residual=match,
                    arrays=str(output.relative_to(ROOT)), arrays_sha256=sha256(output)))
        write_json(folder / 'progress.json', dict(completed=len(results), expected=100))
        print(json.dumps({'proposal':proposal['key'], 'completed':len(results), 'expected':100}), flush=True)
    check_hashes(plan)
    result = dict(**plan, plan_sha256=sha256(folder / 'plan.json'), status='completed_fixed_multirate_diagnostic',
        results=results, rollout_count=len(results), selection_changed=False, scope=spec['scope'])
    write_json(folder / 'experiment.json', result)
    write_json(folder / 'progress.json', dict(status='completed', completed=len(results), expected=100))


if __name__ == '__main__': main()
