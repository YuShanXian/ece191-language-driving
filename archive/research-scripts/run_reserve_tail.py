"""Separate merge-only proposal experiment with explicit target-corridor reserve."""
import copy,inspect,json,shutil
from collections import Counter
from functools import lru_cache
import numpy as np
from shapely.geometry import Point
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from evaluate_candidate_checks import load_graph,current_obstacles
from trajectory_checks import tangent
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.tail_refinement import tail_lateral_shift
from mtr_project.reserve_proposal import evaluate_proposal
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.sources import source_database
from language_selector import action_matches


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def main():
    spec_path=ROOT/'config/reserve-tail-v1.json';spec=json.loads(spec_path.read_text());base=ROOT/'runs/project-v2'/spec['output_tag']
    if base.exists():raise FileExistsError('Use a new version instead of replacing a prior or partial experiment')
    pool_path=ROOT/spec['source_pool'];pool=json.loads(pool_path.read_text())
    for mapping in ['source_sha256','implementation_sha256']:
        for name,expected in pool[mapping].items():
            if digest(ROOT/name)!=expected:raise ValueError('Comparison input changed: '+name)
    base.mkdir(parents=True);write_json(base/'specification.json',spec)
    sources={str(spec_path.relative_to(ROOT)):digest(spec_path),str(pool_path.relative_to(ROOT)):digest(pool_path)}
    vehicle=get_pacifica_parameters();geometry={'wheel_base':vehicle.wheel_base,'rear_axle_to_center':vehicle.rear_axle_to_center}
    windows=[]
    for n,job in enumerate(pool['windows']):
        prior_tag,key=job['run'].split('/')[-2:];source_tag=spec['source_tags'][prior_tag];source=ROOT/'runs/project-v2'/source_tag/key
        name=source_tag+'--'+key;output=base/name
        print('RESERVE',n+1,'/',len(pool['windows']),name,flush=True)
        report=copy.deepcopy(json.loads((source/'anchored_feasibility.json').read_text()));conv_path=ROOT/'samples'/report['summary']['sample']/'conversion.json';conv=json.loads(conv_path.read_text())
        raw=np.load(source/'internal_0000.npz');center=raw['center'];original=np.load(source/'refined_v2_candidates.npz')['world_xy'];trajectories=original.copy()
        if not np.isfinite(original).all() or not np.isfinite(raw['world_xy']).all():raise ValueError('Nonfinite candidates')
        for path in [source/'anchored_feasibility.json',source/'internal_0000.npz',source/'refined_v2_candidates.npz',conv_path,ROOT/conv['source_map'],source_database(conv)]:sources[str(path.relative_to(ROOT))]=digest(path)
        actions=['lane_change_left','lane_change_right'] if job['group']=='development' else ['lane_change_right' if job['group']=='annotation-sequence-v1' else 'lane_change_left']
        candidates=[r for r in report['candidates'] if r['passes_current_checks'] and len(r['route'].get('lane_changes',[]))==1 and not r['route'].get('turns') and r['route']['lane_changes'][0]['action'] in actions]
        accepted=[];attempts=[];eligible_ids={r['candidate'] for r in candidates};graph=None
        if candidates:
            graph,_=add_parallel_connector_edges(load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']))
            obstacles,bad=current_obstacles(conv)
            if bad:raise ValueError('Invalid present obstacles')
        for row in report['candidates']:
            candidate=row['candidate'];idx=candidate-1;source_passed=row['passes_current_checks'];row['source_passed_original_checks']=source_passed
            if candidate not in eligible_ids:
                row['passes_current_checks']=False;row['rejected_by']=list(row['rejected_by'])+['outside_declared_reserve_merge_search'];continue
            action=row['route']['lane_changes'][0]['action'];points=np.vstack([center[:2],original[idx]]).astype(float)
            kwargs={'raw':raw['world_xy'][idx],'center':center,'acceleration':np.asarray(report['summary']['initial_acceleration_from_past_only']),
                'graph':graph,'anchor':report['summary']['past_only_start_node'],'obstacles':obstacles,'action':action,'speed':conv['current_speed_mps'],'geometry':geometry,'margin':spec['target_reserve_m']}
            initial=evaluate_proposal(points,**kwargs,full=True);attempt={'candidate':candidate,'action':action,'initial':initial,'trials':[]};choice=initial if initial['passed'] else None;shift=0.;chosen_points=points;normal=None
            if choice is None and set(initial['rejected_by'])<={'settled_single_merge','target_reserve'}:
                line=graph.nodes[row['route']['node_sequence'][-1]].baseline;projected=np.asarray(line.interpolate(line.project(Point(points[-1]))).coords[0])
                theta=tangent(line,points[-1]);normal=np.array([-np.sin(theta),np.cos(theta)]);requested=float(np.dot(projected-points[-1],normal));maximum=min(abs(requested),spec['maximum_shift_m'])
                amounts=sorted(set([float(x) for x in np.arange(spec['shift_increment_m'],maximum+1e-6,spec['shift_increment_m'])]+([maximum] if maximum>0 else [])))
                for amount in amounts:
                    signed=float(np.sign(requested)*amount);adjusted=tail_lateral_shift(points,normal,signed,start_seconds=spec['tail_start_seconds'])
                    checked=evaluate_proposal(adjusted,**kwargs)
                    attempt['trials'].append({'shift_m':signed,**checked})
                    if checked['passed']:choice=checked;shift=signed;chosen_points=adjusted;break
            if choice is None:
                row['passes_current_checks']=False;row['rejected_by']=['no_verified_reserve_proposal'];row['reserve_initial_reasons']=initial['rejected_by']
            else:
                if choice['skipped_checks']:raise ValueError('Accepted path skipped checks')
                if not np.array_equal(points[:31],chosen_points[:31]):raise ValueError('First3s changed')
                detail=choice['details'];row.update(route=detail['route'],motion=detail['motion'],body=detail['body'],collision=detail['collision'],passes_current_checks=True,rejected_by=[])
                row['reserve_check']=choice;row['refinement']={'method':'quintic tail shift targeting both-heading corridor reserve','signed_shift_m':shift,'target_reserve_m':spec['target_reserve_m'],
                    'tail_start_seconds':spec['tail_start_seconds'],'max_deviation_from_raw_m':detail['maximum_raw_deviation_m'],'within_deviation_bound':True,'max_allowed_deviation_m':1.,'normal':None if normal is None else normal.tolist()}
                trajectories[idx]=chosen_points[1:];accepted.append({'candidate':candidate,'action':action,'shift_m':shift,'maximum_raw_deviation_m':detail['maximum_raw_deviation_m']})
            attempts.append(attempt)
        if not np.array_equal(original[:,:30],trajectories[:,:30]):raise ValueError('Prefix changed')
        report['summary'].update(run=str(output.relative_to(ROOT/'runs')),prediction_source='reserve_targeted_map_tail_experiment',passed_candidates=[r['candidate'] for r in report['candidates'] if r['passes_current_checks']],
            rejection_counts=dict(Counter(x for r in report['candidates'] for x in r['rejected_by'])),scope=spec['scope']+' Only verified single merges in declared directions are selectable; other arrays are unchanged context.')
        report['reserve_tail_experiment']={'source':str(source.relative_to(ROOT)),'actions':actions,'target_reserve_m':spec['target_reserve_m'],'accepted':accepted,'attempts':attempts,'specification_sha256':digest(spec_path)}
        output.mkdir();shutil.copy2(source/'internal_0000.npz',output/'internal_0000.npz');np.savez_compressed(output/'refined_v2_candidates.npz',world_xy=trajectories,scores=raw['scores']);write_json(output/'anchored_feasibility.json',report)
        source_task=job['source_task'];requested=actions if source_task is None else ([source_task['stage']['action']] if source_task['stage']['state']=='active' else [])
        selections={}
        for action in requested:
            eligible=[r for r in report['candidates'] if r['passes_current_checks'] and action_matches(r,action,conv['current_speed_mps'])];selected=max(eligible,key=lambda r:(r['score'],-r['candidate']),default=None)
            selections[action]={'candidate':selected['candidate'] if selected else None,'matching_candidates':[r['candidate'] for r in eligible]}
        window={'key':name,'run':str(output.relative_to(ROOT/'runs')),'source_run':str(source.relative_to(ROOT/'runs')),'prior_run':job['run'],'group':job['group'],
            'gps_seconds':job.get('gps_seconds'),'source_task':source_task,'actions':actions,'accepted':accepted,'selections':selections,'eligible_candidates':len(candidates),'trials':sum(len(a['trials']) for a in attempts),
            'output_sha256':{file:digest(output/file) for file in ['internal_0000.npz','refined_v2_candidates.npz','anchored_feasibility.json']}}
        windows.append(window);write_json(base/'progress.json',{'status':'running','completed_windows':len(windows),'total_windows':len(pool['windows']),'windows':windows})
        print(json.dumps({'accepted':accepted,'selections':selections}),flush=True)
    code=['scripts/run_reserve_tail.py','scripts/mtr_project/reserve_proposal.py','scripts/mtr_project/tail_refinement.py','scripts/mtr_project/corridor_reserve.py','scripts/mtr_project/kinematic_diagnostic.py','scripts/mtr_project/pose_geometry.py','scripts/trajectory_checks.py','scripts/evaluate_candidate_checks.py','scripts/mtr_project/connector_routes.py','scripts/language_selector.py']
    result={'status':'completed','specification':spec,'geometry':geometry,'windows':windows,'source_sha256':sources,'implementation_sha256':{p:digest(ROOT/p) for p in code},'sdk_geometry_sha256':digest(inspect.getfile(get_pacifica_parameters))}
    write_json(base/'experiment.json',result);write_json(base/'progress.json',{'status':'completed','completed_windows':len(windows),'total_windows':len(windows)})
    print(json.dumps({'windows':len(windows),'accepted_paths':sum(len(w['accepted']) for w in windows),'trials':sum(w['trials'] for w in windows)}))


if __name__=='__main__':main()
