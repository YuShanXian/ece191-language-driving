"""Complete passing-pool comparison of extra geometry requirements; no new paths."""
import json,inspect
from collections import Counter
from functools import lru_cache
import numpy as np
from nuplan.common.actor_state.vehicle_parameters import get_pacifica_parameters
from trajectory_checks import headings,tangent,angle_diff
from language_selector import action_matches
from evaluate_candidate_checks import load_graph,current_obstacles
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.kinematic_diagnostic import inverse_center_path
from mtr_project.pose_geometry import check_poses,interpolate_centers_and_angles
from mtr_project.corridor_reserve import target_reserve,choose_guarded,margin_key
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.sources import source_database


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def main():
    spec_path=ROOT/'config/heading-pool-v1.json';spec=json.loads(spec_path.read_text());output=ROOT/spec['output']
    if output.exists():raise FileExistsError('Refuse to replace completed experiment')
    sources={}
    def record(path):sources[str(path.relative_to(ROOT))]=digest(path)
    def read(path):record(path);return json.loads(path.read_text())
    record(spec_path);old=read(ROOT/'runs/project-v2/heading-sensitivity-v1/audit.json')
    for mapping in ['source_sha256','implementation_sha256']:
        for name,expected in old[mapping].items():
            if digest(ROOT/name)!=expected:raise ValueError('Prior diagnostic source changed: '+name)
    cached={(r['run'],r['candidate']):r for r in old['rows']}
    vehicle=get_pacifica_parameters();geometry={'wheel_base':vehicle.wheel_base,'rear_axle_to_center':vehicle.rear_axle_to_center}
    jobs=[]
    for row in read(ROOT/spec['development_manifest']):
        jobs.append({'run':'project-v2/'+spec['development_variant']+'/'+row['key'],'group':'development','source_task':None})
    for path in spec['sequences']:
        report=read(ROOT/path)
        for row in report['checkpoints']:
            jobs.append({'run':row['run'],'group':path.split('/')[2],'source_task':row['selection'],'gps_seconds':row['gps_elapsed_seconds']})
    if len(jobs)!=23 or len({j['run'] for j in jobs})!=23:raise ValueError('Expected 23 distinct checkpoints')
    windows=[];reused=0
    for index,job in enumerate(jobs):
        print('POOL',index+1,'/',len(jobs),job['run'],flush=True)
        folder=ROOT/'runs'/job['run'];screen=read(folder/'anchored_feasibility.json');conv=read(ROOT/'samples'/screen['summary']['sample']/'conversion.json')
        raw_path=folder/'internal_0000.npz';data_path=folder/'refined_v2_candidates.npz';record(raw_path);record(data_path)
        data=np.load(data_path)['world_xy'];center=np.load(raw_path)['center'];passing=[r for r in screen['candidates'] if r['passes_current_checks']]
        entries=[]
        if passing:
            map_path=ROOT/conv['source_map'];record(map_path);record(source_database(conv))
            graph,_=add_parallel_connector_edges(load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']))
            obstacles,bad=current_obstacles(conv)
            if bad:raise ValueError('Invalid current obstacles')
            for row in passing:
                candidate=row['candidate'];points=np.vstack([center[:2],data[candidate-1]]).astype(float)
                initial=float(center[6]);length=float(center[3]);width=float(center[4]);angles=headings(points,initial)
                dense,original=interpolate_centers_and_angles(points,angles)
                inverse=inverse_center_path(dense,initial,**geometry,dt=.05);alternative=inverse['heading']
                cache=cached.get((job['run'],candidate))
                if cache:
                    original_check=cache['original'];changed=cache['alternative'];violations=cache['prior_assigned_route_heading_over_60deg_times'];reused+=1
                else:
                    original_check=check_poses(dense,original,length,width,graph.surface,obstacles)
                    changed=check_poses(dense,alternative,length,width,graph.surface,obstacles)
                    violations=[i*.1 for i,(point,angle,key) in enumerate(zip(points,alternative[::2],row['route']['node_sequence'])) if abs(angle_diff(angle,tangent(graph.nodes[key].baseline,point)))>np.radians(60)]
                if not original_check['body_passed'] or not original_check['cv_collision_passed']:raise ValueError('Cannot reproduce original passing geometry')
                events=row['route'].get('lane_changes',[])
                reserve={margin_key(m):False for m in spec['margins_m']}
                if len(events)==1:
                    event=events[0];target=graph.forward_corridor(event['to'])
                    reserve=target_reserve(dense,[original,alternative],length,width,target,event['step']*.1,spec['margins_m'])
                entries.append({'candidate':candidate,'joint_geometry_passed':changed['body_passed'] and changed['cv_collision_passed'] and not violations,
                    'alternative_body_passed':changed['body_passed'],'alternative_cv_collision_passed':changed['cv_collision_passed'],
                    'assigned_route_heading_concerns':violations,'merge_target_reserve':reserve,
                    'inverse_motion_diagnostic':inverse['summary'],'source_original_geometry_verified':True})
        lookup={r['candidate']:r for r in entries};task=job['source_task'];actions=['lane_change_left','lane_change_right'] if task is None else ([task['stage']['action']] if task['stage']['state']=='active' else [])
        comparisons=[]
        for action in actions:
            eligible=[r for r in passing if action_matches(r,action,conv['current_speed_mps'])]
            original=max(eligible,key=lambda r:(r['score'],-r['candidate']),default=None)
            if task is not None and (original['candidate'] if original else None)!=task['candidate']:raise ValueError('Cannot reproduce persistent original choice')
            comparisons.append({'action':action,'original_candidate':original['candidate'] if original else None,
                'by_margin':{margin_key(m):choose_guarded(screen['candidates'],lookup,action,conv['current_speed_mps'],m) for m in spec['margins_m']}})
        windows.append({**job,'passing_count':len(passing),'audited_candidates':entries,'comparisons':comparisons})
    summary={'windows':len(windows),'passing_candidates_audited':sum(w['passing_count'] for w in windows),'prior_geometry_results_reused':reused,'groups':{}}
    for group in sorted({w['group'] for w in windows}):
        subset=[w for w in windows if w['group']==group];summary['groups'][group]={'windows':len(subset),'actions':{}}
        for action in sorted({c['action'] for w in subset for c in w['comparisons']}):
            comparisons=[c for w in subset for c in w['comparisons'] if c['action']==action]
            summary['groups'][group]['actions'][action]={'active_checkpoints':len(comparisons),'original_proposals':sum(c['original_candidate'] is not None for c in comparisons),
                'by_margin':{margin_key(m):{'proposals':sum(c['by_margin'][margin_key(m)]['candidate'] is not None for c in comparisons),
                    'changed_to_other_candidate':sum(c['by_margin'][margin_key(m)]['candidate'] is not None and c['by_margin'][margin_key(m)]['candidate']!=c['original_candidate'] for c in comparisons)} for m in spec['margins_m']}}
    modules=['scripts/audit_heading_pool.py','scripts/mtr_project/corridor_reserve.py','scripts/mtr_project/pose_geometry.py','scripts/mtr_project/kinematic_diagnostic.py','scripts/trajectory_checks.py','scripts/language_selector.py','scripts/mtr_project/connector_routes.py','scripts/evaluate_candidate_checks.py']
    result={'specification':spec,'geometry':geometry,'summary':summary,'windows':windows,'source_sha256':sources,
        'implementation_sha256':{p:digest(ROOT/p) for p in modules},'sdk_geometry_sha256':digest(inspect.getfile(get_pacifica_parameters))}
    write_json(output,result);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
