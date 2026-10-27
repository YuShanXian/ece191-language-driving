"""Descriptive inverse-bicycle requirements; never change proposal selection."""
import inspect,json,pickle
import numpy as np
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from nuplan.planning.simulation.controller.motion_model.kinematic_bicycle import KinematicBicycleModel
from mtr_project.kinematic_diagnostic import inverse_center_path
from mtr_project.paths import ROOT,sha256,write_json


def main():
    destination=ROOT/'runs/project-v2/kinematic-diagnostic-v1'
    if (destination/'audit.json').exists():raise FileExistsError('Keep historical audit; use a new version for changed diagnostics')
    sources={};vehicle=get_pacifica_parameters();geometry={'wheel_base':vehicle.wheel_base,'rear_axle_to_center':vehicle.rear_axle_to_center}
    def read(path):
        sources[str(path.relative_to(ROOT))]=sha256(path)
        return json.loads(path.read_text())
    manifest=read(ROOT/'runs/project-v2/baseline-v1/development-manifest.json');jobs=[]
    for entry in manifest:
        jobs.append({'sample':entry['sample'],'run':'project-v2/map-tail-development-v1/'+entry['key'],'candidates':'all_passing','group':'development'})
    for base,variant in [('annotation-sequence-v1','map-tail-v1'),('second-annotation-v1','map-tail-second-v1')]:
        report=read(ROOT/'runs/project-v2'/base/f'sequence-report-{variant}.json')
        for row in report['checkpoints']:
            if row['selection']['candidate'] is not None:
                jobs.append({'sample':row['sample'],'run':row['run'],'candidates':[row['selection']['candidate']],'group':base})
    output=[];references=[]
    def measurements(points,heading):
        # Both rates use exactly the same saved coordinates. No fitting/tuning.
        return {str(stride):inverse_center_path(points[::stride],heading,**geometry,dt=.1*stride)['summary'] for stride in [1,2]}
    for job in jobs:
        folder=ROOT/'runs'/job['run'];sample=ROOT/'samples'/job['sample']
        screen=read(folder/'anchored_feasibility.json');conversion=read(sample/'conversion.json')
        raw_path=folder/'internal_0000.npz';derived_path=folder/'refined_v2_candidates.npz';scenario_path=sample/conversion['scenario']
        for path in [raw_path,derived_path,scenario_path]:sources[str(path.relative_to(ROOT))]=sha256(path)
        raw=np.load(raw_path);derived=np.load(derived_path)['world_xy'];center=raw['center'];heading=float(center[6])
        candidates=[r['candidate'] for r in screen['candidates'] if r['passes_current_checks']] if job['candidates']=='all_passing' else job['candidates']
        for candidate in candidates:
            if not screen['candidates'][candidate-1]['passes_current_checks']:raise ValueError('Selected path no longer passes saved screens')
            output.append({'group':job['group'],'run':job['run'],'candidate':candidate,
                'raw':measurements(np.vstack([center[:2],raw['world_xy'][candidate-1]]),heading),
                'derived':measurements(np.vstack([center[:2],derived[candidate-1]]),heading)})
        with scenario_path.open('rb') as stream:state=pickle.load(stream)['tracks']['ego']['state']
        points=state['position'][20:81,:2].astype(float);observed_heading=state['heading'][20:81].astype(float)
        if not np.all(state['valid'][20:81]):raise ValueError('Reference contains invalid observations')
        inverse=inverse_center_path(points,float(observed_heading[0]),**geometry)
        error=np.arctan2(np.sin(inverse['heading']-observed_heading),np.cos(inverse['heading']-observed_heading))
        moving=np.r_[False,inverse['steering_valid']]
        references.append({'sample':job['sample'],'scope':'Recorded future used only here as diagnostic reference; not selection or proposal construction.',
            'metrics':measurements(points,float(observed_heading[0])),
            'moving_heading_samples':int(moving.sum()),
            'peak_abs_heading_error_deg':float(np.max(np.abs(np.degrees(error[moving])))) if moving.any() else None})
    selected=[r for r in output if r['group']!='development']
    sdk_limit=float(inspect.signature(KinematicBicycleModel).parameters['max_steering_angle'].default)*180/np.pi
    result={'geometry':geometry,'dt_seconds':.1,'sensitivity_stride_seconds':{'1':.1,'2':.2},'minimum_forward_speed_mps':.5,
        'integration_max_step_seconds':.005,'method':'Piecewise-linear body-center path; RK4 inverse no-slip rear-axle bicycle. Tire angles evaluated at each segment midpoint; rates only across adjacent evaluable segments.',
        'sdk_default_steering_clamp_deg':sdk_limit,'sdk_limit_note':'SDK simulation default, not a measured vehicle actuator limit. No pass/fail rule added.',
        'summary':{'development_paths':sum(r['group']=='development' for r in output),'actual_annotation_proposals':len(selected),'reference_windows':len(references)},
        'proposals':output,'recorded_references':references,'source_sha256':sources,
        'implementation_sha256':{str(path.relative_to(ROOT)):sha256(path) for path in [ROOT/'scripts/mtr_project/kinematic_diagnostic.py',ROOT/'scripts/audit_proposal_kinematics.py']},
        'sdk_source_sha256':{inspect.getfile(item):sha256(inspect.getfile(item)) for item in [get_pacifica_parameters,KinematicBicycleModel]},
        'limitations':['No closed-loop tracking, tire dynamics, actuator delay/rate calibration, or initial measured tire-angle continuity test.',
            'Piecewise-linear center interpolation has velocity jumps at knots; midpoint steering/rate is a sampled diagnostic and does not prove continuous control feasibility.',
            'Near-zero and reverse speeds are excluded from steering estimates and counted; null does not mean zero or passing.',
            '10Hz/5Hz sensitivity reveals dependence on sampling, not interpolation-independent ground truth.',
            'Recorded future is used only for separate diagnostic reference, never the proposal inverse or selection. Existing choices and frozen sources unchanged.']}
    write_json(destination/'audit.json',result)
    print(json.dumps({'summary':result['summary'],'selected':[{k:r[k] for k in ['run','candidate','derived']} for r in selected]},indent=2))


if __name__=='__main__':main()
