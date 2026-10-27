"""Execute the preregistered full controller comparison, retaining failed trials."""
import inspect
import json
import platform
import numpy as np
from nuplan.common.actor_state.ego_state import EgoState
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.controller.tracker.lqr import LQRTracker
from nuplan.planning.simulation.controller.tracker.ilqr_tracker import ILQRTracker
from nuplan.planning.simulation.controller.tracker.ilqr.ilqr_solver import ILQRSolver
from nuplan.planning.simulation.controller.tracker import tracker_utils
from nuplan.planning.simulation.controller.motion_model.kinematic_bicycle import KinematicBicycleModel
from nuplan.planning.simulation.trajectory.interpolated_trajectory import InterpolatedTrajectory
from evaluate_candidate_checks import load_graph,current_obstacles
from run_multirate_tracking import check_hashes
from mtr_project.controller_comparison import rollout_controller,load_ilqr_config
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.pose_geometry import check_poses
from mtr_project.paths import ROOT,sha256,write_json


def main():
    spec_path=ROOT/'config/controller-comparison-v1.json';spec=json.loads(spec_path.read_text())
    folder=ROOT/'runs/project-v2'/spec['output_tag']
    if folder.exists():raise FileExistsError('Preserve existing controller comparison')
    parent_path=ROOT/spec['source_population'];parent=json.loads(parent_path.read_text())
    verified_path=parent_path.with_name('verification.json');verified=json.loads(verified_path.read_text())
    if verified['experiment_sha256']!=sha256(parent_path) or verified['verifier_sha256']!=sha256(ROOT/'scripts/verify_multirate_tracking.py'):
        raise ValueError('Parent no longer verified')
    check_hashes(parent)
    population=parent['population']
    if len(population)!=spec['expected_unique_proposals'] or len({p['key'] for p in population})!=10:
        raise ValueError('Predeclared population changed')
    receipt_path=ROOT/'config/controller-reference-v1/source-receipt.json';receipt=json.loads(receipt_path.read_text())
    for key in ['lqr_config','ilqr_config']:
        recorded=next(r for r in receipt['configs'] if r['file']==spec[key])
        if sha256(ROOT/spec[key])!=recorded['sha256']:raise ValueError('Official configuration changed')
    lqr=load_lqr_config(ROOT/spec['lqr_config']);ilqr=load_ilqr_config(ROOT/spec['ilqr_config'])
    sources={str(p.relative_to(ROOT)):sha256(p) for p in [spec_path,parent_path,verified_path,receipt_path,
        ROOT/spec['lqr_config'],ROOT/spec['ilqr_config'],ROOT/'runs/project-v2/catalog/ilqr-boundary-probe.json']}
    # These are the exact DB/map/center/reference inputs already checked by the parent.
    sources.update(parent['source_sha256'])
    code=['scripts/run_controller_comparison.py','scripts/mtr_project/controller_comparison.py',
        'scripts/mtr_project/multirate_tracking.py','scripts/mtr_project/tracking_diagnostic.py','scripts/mtr_project/kinematic_diagnostic.py',
        'scripts/mtr_project/pose_geometry.py','scripts/evaluate_candidate_checks.py','scripts/trajectory_checks.py','scripts/run_multirate_tracking.py']
    implementation={name:sha256(ROOT/name) for name in code}
    sdk={inspect.getfile(item):sha256(inspect.getfile(item)) for item in [ILQRTracker,ILQRSolver,LQRTracker,tracker_utils,
        KinematicBicycleModel,EgoState,InterpolatedTrajectory,get_pacifica_parameters]}
    plan=dict(specification=spec,population=population,resolved_controller_configs={'lqr':lqr,'ilqr_iteration_limited':ilqr},
        source_sha256=sources,implementation_sha256=implementation,sdk_source_sha256=sdk,
        runtime={'python':platform.python_version(),'numpy':np.__version__,'platform':platform.platform(),
                 'threads':'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1; command latency descriptive only'})
    folder.mkdir();write_json(folder/'plan.json',plan);results=[]
    for proposal in population:
        screen=json.loads((ROOT/proposal['screen']).read_text());conv=json.loads((ROOT/proposal['conversion']).read_text())
        center=np.load(ROOT/'runs'/proposal['window']['run']/'internal_0000.npz')['center']
        points=np.load(ROOT/proposal['reference_arrays'])['target_center_xy']
        graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);obstacles,bad=current_obstacles(conv)
        if bad:raise ValueError('Invalid current actors')
        for controller in spec['controllers']:
            for tire in spec['initial_tire_angles_deg']:
                arrays,metrics,diagnostics,failure=rollout_controller(points,float(center[6]),center[7:9],
                    screen['summary']['initial_acceleration_from_past_only'],tire,controller,lqr,ilqr,spec['motion_model'],
                    duration=spec['simulation_duration_seconds'],control_dt=spec['control_dt_seconds'],
                    integration_dt=spec['integration_dt_seconds'],reference_dt=spec['reference_dt_seconds'])
                geometry=None if len(arrays['time_s'])<2 else check_poses(arrays['center_xy'],arrays['heading'],float(center[3]),
                    float(center[4]),graph.surface,obstacles,dt=spec['integration_dt_seconds'])
                key=proposal['key']+f'--{controller}--steer{tire:+.1f}';output=folder/(key+'.npz');np.savez_compressed(output,**arrays)
                results.append(dict(key=key,proposal=proposal['key'],controller=controller,initial_tire_angle_deg=tire,
                    status='failed' if failure is not None else 'completed',failure=failure,metrics=metrics,diagnostics=diagnostics,
                    simulated_pose_checks=geometry,arrays=str(output.relative_to(ROOT)),arrays_sha256=sha256(output)))
                print(json.dumps({'completed':len(results),'total':60,'case':key,'status':results[-1]['status'],
                    'max_error_m':metrics['maximum_center_error_m'],'road':geometry['body_passed'] if geometry else None}),flush=True)
        write_json(folder/'progress.json',{'completed':len(results),'total':60})
    check_hashes(plan)
    result=dict(**plan,plan_sha256=sha256(folder/'plan.json'),status='completed_all_predeclared_trials',results=results,
        rollout_count=len(results),failed_trials=sum(r['status']=='failed' for r in results),selection_changed=False,scope=spec['scope'])
    write_json(folder/'experiment.json',result);write_json(folder/'progress.json',{'status':result['status'],'completed':len(results),'total':60})


if __name__=='__main__':main()
