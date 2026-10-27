"""Run the fixed full accepted-proposal population through official feedback tracking."""
import inspect,json
from collections import Counter
from pathlib import Path
import numpy as np
import yaml
from nuplan.common.actor_state.ego_state import EgoState
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.controller.tracker.lqr import LQRTracker
from nuplan.planning.simulation.controller.tracker import tracker_utils
from nuplan.planning.simulation.controller.motion_model.kinematic_bicycle import KinematicBicycleModel
from nuplan.planning.simulation.trajectory.interpolated_trajectory import InterpolatedTrajectory
from evaluate_candidate_checks import load_graph,current_obstacles
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.corridor_reserve import target_reserve,margin_key
from mtr_project.pose_geometry import check_poses
from mtr_project.tracking_diagnostic import track_frozen_path,load_lqr_config
from mtr_project.paths import ROOT,sha256,write_json


def main():
    spec_path=ROOT/'config/tracking-diagnostic-v1.json';spec=json.loads(spec_path.read_text())
    dest=ROOT/'runs/project-v2'/spec['output_tag']
    if dest.exists():raise FileExistsError('Preserve this experiment; use a new version')
    experiment_path=ROOT/spec['source_experiment'];experiment=json.loads(experiment_path.read_text())
    verification_path=experiment_path.with_name('verification.json');verification=json.loads(verification_path.read_text())
    if verification['experiment_sha256']!=sha256(experiment_path):raise ValueError('Source experiment no longer verified')
    source_receipt=ROOT/'config/controller-reference-v1/source-receipt.json';official=json.loads(source_receipt.read_text())
    config_path=ROOT/spec['tracker_config']
    source=next(x for x in official['configs'] if x['file']==spec['tracker_config'])
    if sha256(config_path)!=source['sha256']:raise ValueError('Pinned official controller config changed')
    controller=load_lqr_config(config_path)
    sources={str(p.relative_to(ROOT)):sha256(p) for p in [spec_path,experiment_path,verification_path,source_receipt,config_path]}
    code=['scripts/run_tracking_diagnostic.py','scripts/mtr_project/tracking_diagnostic.py','scripts/mtr_project/kinematic_diagnostic.py','scripts/mtr_project/pose_geometry.py',
          'scripts/mtr_project/corridor_reserve.py','scripts/mtr_project/connector_routes.py','scripts/evaluate_candidate_checks.py','scripts/trajectory_checks.py']
    implementation={p:sha256(ROOT/p) for p in code}
    sdk={inspect.getfile(x):sha256(inspect.getfile(x)) for x in [LQRTracker,tracker_utils,KinematicBicycleModel,EgoState,InterpolatedTrajectory,get_pacifica_parameters]}
    jobs=[w for w in experiment['windows'] if w['accepted']];count=sum(len(w['accepted']) for w in jobs)
    if count!=9:raise ValueError('Predeclared population changed')
    dest.mkdir();write_json(dest/'specification.json',spec);output=[]
    for window in jobs:
        folder=ROOT/'runs'/window['run'];screen_path=folder/'anchored_feasibility.json';screen=json.loads(screen_path.read_text())
        for name,digest in window['output_sha256'].items():
            path=folder/name
            if sha256(path)!=digest:raise ValueError('Proposal changed: '+str(path))
            sources[str(path.relative_to(ROOT))]=digest
        conversion_path=ROOT/'samples'/screen['summary']['sample']/'conversion.json';conversion=json.loads(conversion_path.read_text());sources[str(conversion_path.relative_to(ROOT))]=sha256(conversion_path)
        raw=np.load(folder/'internal_0000.npz');center=raw['center'];proposals=np.load(folder/'refined_v2_candidates.npz')['world_xy']
        graph,_=add_parallel_connector_edges(load_graph(np.asarray(conversion['origin_xy_m']),conversion['source_epsg'],conversion['source_map']))
        map_path=ROOT/conversion['source_map'];sources[str(map_path.relative_to(ROOT))]=sha256(map_path)
        obstacles,bad=current_obstacles(conversion)
        if bad:raise ValueError('Invalid current actor states')
        for accepted in window['accepted']:
            candidate=accepted['candidate'];record=screen['candidates'][candidate-1]
            points=np.vstack([center[:2],proposals[candidate-1]]).astype(float)
            dense=np.empty((len(points)*2-1,2));dense[::2]=points;dense[1::2]=(points[:-1]+points[1:])/2
            event=record['route']['lane_changes'][0];target=graph.forward_corridor(event['to'])
            for dt in spec['integration_dt_seconds']:
                for tire in spec['initial_tire_angles_deg']:
                    key=f'{window["key"]}--q{candidate:02d}--dt{dt:.2f}--steer{tire:+.1f}'
                    print('TRACK',len(output)+1,'/',count*6,key,flush=True)
                    arrays,metrics=track_frozen_path(dense,float(center[6]),center[7:9],screen['summary']['initial_acceleration_from_past_only'],tire,controller,spec['motion_model'],simulation_dt=dt)
                    geometry=check_poses(arrays['center_xy'],arrays['heading'],float(center[3]),float(center[4]),graph.surface,obstacles,dt=dt)
                    reserve=target_reserve(arrays['center_xy'],[arrays['heading']],float(center[3]),float(center[4]),target,0.,[spec['target_corridor_reserve_m']],dt=dt)
                    output_path=dest/(key+'.npz');np.savez_compressed(output_path,**arrays)
                    selected=window['selections'].get(accepted['action'],{}).get('candidate')==candidate
                    result={'key':key,'window':window['key'],'group':window['group'],'candidate':candidate,'action':accepted['action'],'was_selected_by_original_score':selected,
                            'simulation_dt':dt,'initial_tire_angle_deg':tire,'metrics':metrics,'simulated_pose_checks':geometry,
                            'final_half_second_target_reserve':reserve[margin_key(spec['target_corridor_reserve_m'])],
                            'arrays':str(output_path.relative_to(ROOT)),'arrays_sha256':sha256(output_path)}
                    output.append(result);write_json(dest/'progress.json',{'status':'running','completed':len(output),'total':count*6,'results':output})
                    print(json.dumps({'error_m':metrics['maximum_center_error_m'],'body':geometry['body_passed'],'cv':geometry['cv_collision_passed'],'target':result['final_half_second_target_reserve']}),flush=True)
    for name,digest in {**sources,**implementation}.items():
        if sha256(ROOT/name)!=digest:raise ValueError('Input/source changed during experiment: '+name)
    result={'status':'completed_fixed_tracking_diagnostic','specification':spec,'proposal_count':count,'rollout_count':len(output),'results':output,
            'source_sha256':sources,'implementation_sha256':implementation,'sdk_source_sha256':sdk,
            'scope':spec['scope'],'selection_changed':False,'full_nuplan_benchmark':False}
    write_json(dest/'experiment.json',result);write_json(dest/'progress.json',{'status':'completed','completed':len(output),'total':count*6})
    print(json.dumps({'proposals':count,'rollouts':len(output),'directory':str(dest)},indent=2))


if __name__=='__main__':main()
