"""Run or verify all preregistered terminal-hold trials; full-time geometry avoids resetting the CV clock."""
import argparse,json
from functools import lru_cache
import numpy as np
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.terminal_hold import extend_hold,assert_terminal_contract
from mtr_project.controller_comparison import summarize_arrays
from mtr_project.pose_geometry import check_poses
from evaluate_candidate_checks import load_graph,current_obstacles
from verify_tracking_diagnostic import verify_transitions


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def arrays(path):
    with np.load(ROOT/path,allow_pickle=False) as f:return {k:f[k] for k in f.files}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    spec_path=ROOT/'config/controller-terminal-hold-v1.json';spec=json.loads(spec_path.read_text())
    folder=ROOT/'runs/project-v2'/spec['output_tag'];path=folder/'experiment.json'
    parent_path=ROOT/spec['source_experiment'];parent=json.loads(parent_path.read_text());receipt_path=parent_path.with_name('verification.json')
    receipt=json.loads(receipt_path.read_text())
    if receipt['experiment_sha256']!=digest(parent_path) or receipt['verifier_sha256']!=digest(ROOT/'scripts/verify_controller_comparison.py') or receipt['trials_rechecked']!=60:
        raise ValueError('Parent is no longer verified')
    for mapping in [parent['source_sha256'],parent['implementation_sha256'],parent['sdk_source_sha256']]:
        for name,expected in mapping.items():
            if digest(ROOT/name)!=expected:raise ValueError('Parent source changed: '+name)
    if len(parent['results'])!=spec['expected_parent_trials'] or len({r['key'] for r in parent['results']})!=60:raise ValueError('Parent population changed')
    source_paths=[spec_path,parent_path,receipt_path,ROOT/'scripts/run_terminal_hold.py',ROOT/'scripts/mtr_project/terminal_hold.py',ROOT/'scripts/verify_tracking_diagnostic.py']
    sources={str(p.relative_to(ROOT)):digest(p) for p in source_paths}
    plan=dict(specification=spec,parent_experiment_sha256=digest(parent_path),source_sha256=sources,
        population=[r['key'] for r in parent['results']],selection_changed=False)
    if args.verify:
        result=json.loads(path.read_text())
        for key,value in plan.items():
            if result[key]!=value:raise ValueError('Inputs or population changed')
        if digest(folder/'plan.json')!=result['plan_sha256'] or json.loads((folder/'plan.json').read_text())!=plan:raise ValueError('Plan changed')
        if len(result['results'])!=60 or [r['key'] for r in result['results']]!=plan['population']:raise ValueError('Incomplete results')
        saved_rows={r['key']:r for r in result['results']}
    else:
        if folder.exists():raise FileExistsError('Preserve existing terminal experiment')
        folder.mkdir();write_json(folder/'plan.json',plan)
    dt=spec['integration_dt_seconds'];motion=parent['specification']['motion_model']
    effective={**motion,'accel_time_constant_seconds':0.,'steering_angle_time_constant_seconds':0.}
    rows=[];checks=[];context={}
    for original in parent['results']:
        key=original['key'];proposal=next(p for p in parent['population'] if p['key']==original['proposal'])
        if digest(ROOT/original['arrays'])!=original['arrays_sha256']:raise ValueError('Parent rollout changed')
        if original['status']!='completed':
            row=dict(key=key,status='incomplete_parent',parent_status=original['status'],parent_failure=original['failure'],arrays=None)
            if args.verify and row!=saved_rows[key]:raise ValueError('Failure was hidden')
            rows.append(row);continue
        before=arrays(original['arrays']);reference=arrays(proposal['reference_arrays'])
        if args.verify:
            row=saved_rows[key]
            if digest(ROOT/row['arrays'])!=row['arrays_sha256']:raise ValueError('Terminal arrays changed')
            data=arrays(row['arrays'])
        else:
            data=extend_hold(before,reference,motion,dt,spec['parent_duration_seconds'],spec['target_duration_seconds'])
        assert_terminal_contract(before,reference,data,dt)
        residual=verify_transitions(data,effective,dt)
        if proposal['key'] not in context:
            conv=json.loads((ROOT/proposal['conversion']).read_text());center=arrays('runs/'+proposal['window']['run']+'/internal_0000.npz')['center']
            graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);obstacles,bad=current_obstacles(conv)
            if bad:raise ValueError('Invalid current actors')
            context[proposal['key']]=(center,graph,obstacles)
        center,graph,obstacles=context[proposal['key']]
        geometry=check_poses(data['center_xy'],data['heading'],float(center[3]),float(center[4]),graph.surface,obstacles,dt=dt)
        metrics=summarize_arrays(data,motion,dt);metrics['completed_duration_seconds']=float(data['time_s'][-1])
        changes={field:bool(original['simulated_pose_checks'][field] and not geometry[field]) for field in ['body_passed','cv_collision_passed']}
        output=folder/(key+'.npz')
        if not args.verify:np.savez_compressed(output,**data)
        expected=dict(key=key,proposal=original['proposal'],controller=original['controller'],initial_tire_angle_deg=original['initial_tire_angle_deg'],
            status='completed_terminal_hold',arrays=str(output.relative_to(ROOT)),arrays_sha256=digest(output),metrics=metrics,
            simulated_pose_checks=geometry,parent_metrics=original['metrics'],parent_pose_checks=original['simulated_pose_checks'],
            passing_checks_lost=changes,appended_steps=len(data['time_s'])-len(before['time_s']))
        if args.verify and row!=expected:raise ValueError('Recomputed terminal result differs: '+key)
        rows.append(expected);checks.append(dict(key=key,exact_prefix=True,held_commands=True,original_reference=True,
            full_elapsed_time_geometry=True,motion_transition_max_residual=residual))
        print(('VERIFIED' if args.verify else 'COMPLETED'),len(rows),key,'road',geometry['body_passed'],flush=True)
    if args.verify:
        verified=dict(status='passed_terminal_hold_contract',experiment_sha256=digest(path),verifier_sha256=digest(__file__),
            trials_rechecked=len(checks),appended_transitions=sum(r.get('appended_steps',0) for r in rows),checks=checks,
            scope='Exact inherited prefix; no new controller/filter update; original target; all full-horizon motion transitions and geometry recomputed. Shared SDK/model, not physical truth.')
        write_json(folder/'verification.json',verified)
    else:
        write_json(path,dict(**plan,plan_sha256=digest(folder/'plan.json'),results=rows,status='completed_predeclared_population',scope=spec['scope']))
    print(json.dumps(dict(status='verified' if args.verify else 'completed',trials=len(rows),checks_lost={k:sum(r.get('passing_checks_lost',{}).get(k,False) for r in rows) for k in ['body_passed','cv_collision_passed']})))


if __name__=='__main__':main()
