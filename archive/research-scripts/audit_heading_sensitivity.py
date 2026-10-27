"""Isolate body-heading assumptions while preserving every proposed center point."""
import json
from collections import defaultdict
from functools import lru_cache
import numpy as np
from trajectory_checks import headings,footprint,tangent,angle_diff
from evaluate_candidate_checks import load_graph,current_obstacles
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.kinematic_diagnostic import inverse_center_path
from mtr_project.pose_geometry import check_poses,interpolate_centers_and_angles
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.sources import source_database


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def main():
    config_path=ROOT/'config/heading-sensitivity-v1.json';spec=json.loads(config_path.read_text());output=ROOT/spec['output']
    if output.exists():raise FileExistsError('Historical audit already exists')
    source_path=ROOT/spec['input_audit'];audit=json.loads(source_path.read_text());sources={str(config_path.relative_to(ROOT)):digest(config_path),str(source_path.relative_to(ROOT)):digest(source_path)}
    for name,expected in audit['source_sha256'].items():
        if digest(ROOT/name)!=expected:raise ValueError('Original diagnostic input changed: '+name)
    groups=defaultdict(list)
    for row in audit['proposals']:groups[row['run']].append(row)
    rows=[]
    for run,entries in groups.items():
        print('CHECK BODY',run,flush=True)
        folder=ROOT/'runs'/run;screen_path=folder/'anchored_feasibility.json';screen=json.loads(screen_path.read_text())
        conv_path=ROOT/'samples'/screen['summary']['sample']/'conversion.json';conv=json.loads(conv_path.read_text())
        data_path=folder/'refined_v2_candidates.npz';raw_path=folder/'internal_0000.npz';data=np.load(data_path)['world_xy'];center=np.load(raw_path)['center']
        map_path=ROOT/conv['source_map'];db=source_database(conv)
        for path in [screen_path,conv_path,data_path,raw_path,map_path,db]:sources[str(path.relative_to(ROOT))]=digest(path)
        graph,_=add_parallel_connector_edges(load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']))
        obstacles,bad=current_obstacles(conv)
        if bad:raise ValueError('Incomplete present actors')
        for entry in entries:
            candidate=entry['candidate'];saved=screen['candidates'][candidate-1]
            if not saved['passes_current_checks']:raise ValueError('Audit population changed')
            points=np.vstack([center[:2],data[candidate-1]]).astype(float);initial=float(center[6]);length=float(center[3]);width=float(center[4])
            original_angles=headings(points,initial);dense,original_dense=interpolate_centers_and_angles(points,original_angles)
            inverse=inverse_center_path(dense,initial,**audit['geometry'],dt=spec['dt_seconds']);alternative=inverse['heading']
            baseline=check_poses(dense,original_dense,length,width,graph.surface,obstacles,dt=spec['dt_seconds'])
            if baseline['body_passed']!=saved['body']['passed'] or baseline['cv_collision_passed']!=saved['collision']['passed']:
                raise ValueError('Original pose replay does not reproduce saved screens')
            changed=check_poses(dense,alternative,length,width,graph.surface,obstacles,dt=spec['dt_seconds'])
            events=[]
            for event in saved['route'].get('lane_changes',[]):
                target=graph.forward_corridor(event['to']);enough=event['step']<=len(points)-6
                original=bool(enough and all(target.covers(footprint(p,h,length,width)) for p,h in zip(points[-6:],original_angles[-6:])))
                if original!=event['settled_for_last_half_second']:raise ValueError('Original target settling changed')
                new=bool(enough and all(target.covers(footprint(p,h,length,width)) for p,h in zip(points[-6:],alternative[::2][-6:])))
                events.append({'action':event['action'],'from':event['from'],'to':event['to'],'original_settled':original,'alternative_settled':new})
            disagreement=np.abs(np.degrees(np.arctan2(np.sin(alternative-original_dense),np.cos(alternative-original_dense))))
            route_violation=[]
            for i,(point,angle,key) in enumerate(zip(points,alternative[::2],saved['route']['node_sequence'])):
                if abs(angle_diff(angle,tangent(graph.nodes[key].baseline,point)))>np.radians(60):route_violation.append(i*.1)
            rows.append({'run':run,'group':entry['group'],'candidate':candidate,'maximum_body_heading_difference_deg':float(disagreement.max()),
                'original':baseline,'alternative':changed,'lane_change_settling':events,'prior_assigned_route_heading_over_60deg_times':route_violation,
                'new_geometry_concern':not changed['body_passed'] or not changed['cv_collision_passed'] or any(e['original_settled'] and not e['alternative_settled'] for e in events) or bool(route_violation)})
    result={'specification':spec,'rows':rows,'summary':{'paths':len(rows),'original_geometry_reproduced':len(rows),
        'alternative_road_failures':sum(not r['alternative']['body_passed'] for r in rows),
        'alternative_cv_collisions':sum(not r['alternative']['cv_collision_passed'] for r in rows),
        'lost_target_settling':sum(any(e['original_settled'] and not e['alternative_settled'] for e in r['lane_change_settling']) for r in rows),
        'prior_route_heading_concerns':sum(bool(r['prior_assigned_route_heading_over_60deg_times']) for r in rows),
        'actual_annotation_proposals_with_new_concern':sum(r['group']!='development' and r['new_geometry_concern'] for r in rows)},
        'source_sha256':sources,'generator_sha256':digest(ROOT/'scripts/audit_heading_sensitivity.py'),
        'implementation_sha256':{name:digest(ROOT/name) for name in ['scripts/mtr_project/pose_geometry.py','scripts/mtr_project/kinematic_diagnostic.py','scripts/trajectory_checks.py','scripts/evaluate_candidate_checks.py','scripts/mtr_project/connector_routes.py']}}
    write_json(output,result);print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':main()
