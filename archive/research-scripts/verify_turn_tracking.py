"""Recompute all six turn tracking transitions, geometry and descriptive deviations."""
import json
from functools import lru_cache
import numpy as np
from shapely.geometry import Point
from evaluate_candidate_checks import load_graph,current_obstacles
from trajectory_checks import footprint
from mtr_project.pose_geometry import check_poses
from mtr_project.paths import ROOT,sha256,write_json
from verify_tracking_diagnostic import verify_transitions


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def main():
    base=ROOT/'runs/project-v2/turn-tracking-v1';path=base/'experiment.json';experiment=json.loads(path.read_text());spec=experiment['specification']
    parent=json.loads((ROOT/spec['source_evaluation']).read_text());window_plan=json.loads((ROOT/'runs/project-v2/turn-challenge-v1/window-plan.json').read_text())
    for source in [experiment,parent,window_plan]:
        for mapping in [source['source_sha256'],source['implementation_sha256'],source.get('sdk_source_sha256',{})]:
            for name,expected in mapping.items():
                if digest(ROOT/name)!=expected:raise ValueError('Changed dependency: '+name)
    expected={(item['window']['key'],item['candidate'],dt,angle) for item in experiment['population'] for dt in spec['integration_dt_seconds'] for angle in spec['initial_tire_angles_deg']}
    actual={(r['window']['key'],r['candidate'],r['simulation_dt'],r['initial_tire_angle_deg']) for r in experiment['results']}
    if expected!=actual or len(experiment['results'])!=6 or len(actual)!=6:raise ValueError('Incomplete/duplicate grid')
    checks=[]
    for item in experiment['population']:
        window=item['window'];source=ROOT/'runs'/window['run'];screen=json.loads((source/'anchored_feasibility.json').read_text());center=np.load(source/'internal_0000.npz')['center'];conv=json.loads((ROOT/'samples'/window['sample']/'conversion.json').read_text())
        graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);obstacles,bad=current_obstacles(conv)
        if bad:raise ValueError('Invalid observed actors')
        for row in experiment['results']:
            if row['window']!=window:continue
            array_path=ROOT/row['arrays']
            if sha256(array_path)!=row['arrays_sha256']:raise ValueError('Changed rollout')
            with np.load(array_path,allow_pickle=False) as saved:data={k:saved[k] for k in saved.files}
            dt=row['simulation_dt'];n=round(6/dt)+1
            if data['center_xy'].shape!=(n,2) or data['commands_accel_and_tire_rate'].shape!=(n-1,2) or any(not np.isfinite(a).all() for a in data.values()):raise ValueError('Invalid rollout shape/values')
            np.testing.assert_allclose(data['time_s'],np.arange(n)*dt,atol=1e-12,rtol=0);np.testing.assert_allclose(data['center_xy'][0],center[:2],atol=1e-9,rtol=0)
            residual=verify_transitions(data,spec['motion_model'],dt)
            geometry=check_poses(data['center_xy'],data['heading'],float(center[3]),float(center[4]),graph.surface,obstacles,dt=dt)
            if geometry!=row['simulated_pose_checks']:raise ValueError('Body/CV result differs')
            errors=np.linalg.norm(data['center_xy']-data['target_center_xy'],axis=1)
            if not np.isclose(errors.max(),row['metrics']['maximum_center_error_m'],rtol=0,atol=1e-10):raise ValueError('Error summary differs')
            heading=float(np.degrees(np.unwrap(data['heading'])[-1]-data['heading'][0]))
            if not np.isclose(heading,row['simulated_heading_progress_deg'],rtol=0,atol=1e-10):raise ValueError('Heading summary differs')
            worst=None
            for t,position,angle in zip(data['time_s'],data['center_xy'],data['heading']):
                body=footprint(position,angle,float(center[3]),float(center[4]));area=float(body.difference(graph.surface).area)
                if worst is None or area>worst['outside_area_m2']:
                    worst={'time_s':float(t),'outside_area_m2':area,'maximum_vertex_outside_m':max(Point(p).distance(graph.surface) for p in body.exterior.coords)}
            checks.append({'key':row['key'],'maximum_motion_transition_residual':residual,'first_outside_time_s':geometry['outside_times_seconds'][0] if geometry['outside_times_seconds'] else None,'worst_body_overlap':worst})
    result={'status':'passed_declared_turn_tracking_checks','experiment_sha256':sha256(path),'rollouts_rechecked':len(checks),'checks':checks,
            'verifier_sha256':sha256(__file__),'transition_verifier_sha256':sha256(ROOT/'scripts/verify_tracking_diagnostic.py'),
            'scope':'Complete six-case grid and logged-command motion transitions rechecked; same road and actor predicates, not independent physical truth. Outside distance is sampled vehicle vertices, not a continuous swept-volume bound.'}
    write_json(base/'verification.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
