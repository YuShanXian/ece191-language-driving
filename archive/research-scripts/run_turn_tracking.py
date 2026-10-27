"""Fixed sensitivity grid for every selected turn candidate in the new challenge."""
import inspect,json
import numpy as np
from nuplan.common.actor_state.ego_state import EgoState
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.controller.tracker.lqr import LQRTracker
from nuplan.planning.simulation.controller.tracker import tracker_utils
from nuplan.planning.simulation.controller.motion_model.kinematic_bicycle import KinematicBicycleModel
from nuplan.planning.simulation.trajectory.interpolated_trajectory import InterpolatedTrajectory
from evaluate_candidate_checks import load_graph,current_obstacles
from mtr_project.pose_geometry import check_poses
from mtr_project.tracking_diagnostic import track_frozen_path,load_lqr_config
from mtr_project.paths import ROOT,sha256,write_json


def main():
    spec_path=ROOT/'config/turn-tracking-v1.json';spec=json.loads(spec_path.read_text());parent_path=ROOT/spec['source_evaluation'];parent=json.loads(parent_path.read_text())
    verified_path=parent_path.with_name('verification.json');verified=json.loads(verified_path.read_text())
    if verified['evaluation_sha256']!=sha256(parent_path):raise ValueError('Turn population not verified')
    for mapping in [parent['source_sha256'],parent['implementation_sha256']]:
        for name,digest in mapping.items():
            if sha256(ROOT/name)!=digest:raise ValueError('Parent changed: '+name)
    configuration=ROOT/spec['tracker_config'];official_path=ROOT/'config/controller-reference-v1/source-receipt.json';official=json.loads(official_path.read_text())
    source=next(r for r in official['configs'] if r['file']==spec['tracker_config'])
    if sha256(configuration)!=source['sha256']:raise ValueError('Official controller config changed')
    population=[]
    for window in parent['windows']:
        for choice in window['choices']:
            candidate=choice['all64']['candidate']
            if candidate is not None and not any(r['window']['key']==window['window']['key'] and r['candidate']==candidate for r in population):
                population.append({'window':window['window'],'candidate':candidate,'action':choice['action']})
    if len(population)!=spec['expected_unique_proposals']:raise ValueError('Population differs from declared count')
    folder=ROOT/'runs/project-v2'/spec['output_tag']
    if folder.exists():raise FileExistsError('Preserve prior tracking version')
    sources={str(p.relative_to(ROOT)):sha256(p) for p in [spec_path,parent_path,verified_path,configuration,official_path]}
    code=['scripts/run_turn_tracking.py','scripts/mtr_project/tracking_diagnostic.py','scripts/mtr_project/kinematic_diagnostic.py','scripts/mtr_project/pose_geometry.py','scripts/evaluate_candidate_checks.py','scripts/trajectory_checks.py']
    implementation={p:sha256(ROOT/p) for p in code};sdk={inspect.getfile(x):sha256(inspect.getfile(x)) for x in [LQRTracker,tracker_utils,KinematicBicycleModel,EgoState,InterpolatedTrajectory,get_pacifica_parameters]}
    controller=load_lqr_config(configuration);results=[];folder.mkdir();write_json(folder/'specification.json',spec)
    for item in population:
        window=item['window'];source_folder=ROOT/'runs'/window['run'];screen=json.loads((source_folder/'anchored_feasibility.json').read_text());conv_path=ROOT/'samples'/window['sample']/'conversion.json';conv=json.loads(conv_path.read_text())
        center=np.load(source_folder/'internal_0000.npz')['center'];paths=np.load(source_folder/'refined_v2_candidates.npz')['world_xy'];points=np.vstack([center[:2],paths[item['candidate']-1]]).astype(float)
        dense=np.empty((len(points)*2-1,2));dense[::2]=points;dense[1::2]=(points[:-1]+points[1:])/2
        graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);obstacles,bad=current_obstacles(conv)
        if bad:raise ValueError('Invalid current actors')
        for name in ['source_map','source_db']:
            path=ROOT/conv[name];sources[str(path.relative_to(ROOT))]=sha256(path)
        for dt in spec['integration_dt_seconds']:
            for angle in spec['initial_tire_angles_deg']:
                arrays,metrics=track_frozen_path(dense,float(center[6]),center[7:9],screen['summary']['initial_acceleration_from_past_only'],angle,controller,spec['motion_model'],simulation_dt=dt)
                geometry=check_poses(arrays['center_xy'],arrays['heading'],float(center[3]),float(center[4]),graph.surface,obstacles,dt=dt)
                heading_progress=float(np.degrees(np.unwrap(arrays['heading'])[-1]-arrays['heading'][0]))
                key=window['key']+f'--q{item["candidate"]:02d}--dt{dt:.2f}--steer{angle:+.1f}';array_path=folder/(key+'.npz');np.savez_compressed(array_path,**arrays)
                result={'key':key,'window':window,'candidate':item['candidate'],'action':item['action'],'simulation_dt':dt,'initial_tire_angle_deg':angle,
                        'metrics':metrics,'simulated_heading_progress_deg':heading_progress,'simulated_pose_checks':geometry,'arrays':str(array_path.relative_to(ROOT)),'arrays_sha256':sha256(array_path)}
                results.append(result);write_json(folder/'progress.json',{'completed':len(results),'expected':len(population)*6,'results':results})
                print(json.dumps({'case':key,'max_error_m':metrics['maximum_center_error_m'],'heading_progress_deg':heading_progress,'road':geometry['body_passed'],'cv':geometry['cv_collision_passed']}),flush=True)
    for name,digest in {**sources,**implementation,**sdk}.items():
        if sha256(ROOT/name)!=digest:raise ValueError('Source changed during rollout: '+name)
    result={'status':'completed_fixed_turn_tracking','specification':spec,'population':population,'results':results,'source_sha256':sources,'implementation_sha256':implementation,'sdk_source_sha256':sdk,'scope':spec['scope'],'selection_changed':False}
    write_json(folder/'experiment.json',result);write_json(folder/'progress.json',{'status':'completed','completed':len(results),'expected':len(population)*6})


if __name__=='__main__':main()
