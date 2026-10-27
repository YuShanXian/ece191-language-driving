"""Try minimal tested map-guided tail shifts, then repeat all candidate checks."""
import argparse,json,shutil
from collections import Counter
import numpy as np
from shapely.geometry import Point
from evaluate_candidate_checks import load_graph,current_obstacles
from trajectory_checks import motion_check,collision_check,tangent
from mtr_project.connector_routes import add_parallel_connector_edges
from mtr_project.tail_refinement import tail_lateral_shift
from mtr_project.paths import ROOT,write_json,sha256
from language_selector import action_matches
from compare_connector_routes import checked_relative


def refine_case(key,source_tag='connector-route-v1',output_tag='map-tail-v1',actions=('lane_change_right',)):
    source=ROOT/'runs/project-v2'/checked_relative(source_tag)/checked_relative(key)
    output=ROOT/'runs/project-v2'/checked_relative(output_tag)/checked_relative(key)
    if (output/'anchored_feasibility.json').exists():raise ValueError('Preserve prior experiment')
    report=json.loads((source/'anchored_feasibility.json').read_text())
    conv=json.loads((ROOT/'samples'/report['summary']['sample']/'conversion.json').read_text())
    graph,_=add_parallel_connector_edges(load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']))
    anchor=report['summary']['past_only_start_node'];obstacles,bad=current_obstacles(conv)
    raw=np.load(source/'internal_0000.npz');center=raw['center']
    trajectories=np.load(source/'refined_v2_candidates.npz')['world_xy'].copy()
    acceleration=np.asarray(report['summary']['initial_acceleration_from_past_only']);trials=[];modified=[]
    for row in report['candidates']:
        events=row['route'].get('lane_changes',[])
        # Only attempt a complete single-merge topology already supported
        # by the candidate; do not invent a second maneuver or repair collisions.
        if not row['passes_current_checks'] or len(events)!=1 or events[0]['action'] not in actions or row['route'].get('turns'):continue
        action=events[0]['action']
        if action_matches(row,action,conv['current_speed_mps']):continue
        idx=row['candidate']-1;points=np.vstack([center[:2],trajectories[idx]])
        line=graph.nodes[row['route']['node_sequence'][-1]].baseline
        projected=np.asarray(line.interpolate(line.project(Point(points[-1]))).coords[0])
        angle=tangent(line,points[-1]);normal=np.array([-np.sin(angle),np.cos(angle)])
        requested=float(np.dot(projected-points[-1],normal));maximum=min(abs(requested),1.)
        amounts=sorted(set([float(x) for x in np.arange(.05,maximum+.000001,.05)]+([maximum] if maximum>0 else [])))
        for amount in amounts:
            adjusted=tail_lateral_shift(points,normal,np.sign(requested)*amount)
            route=graph.match(adjusted,float(center[6]),start_nodes={anchor})
            graph.settled_lane_changes(route,adjusted,float(center[6]),float(center[3]),float(center[4]))
            body=graph.body_check(adjusted,float(center[6]),float(center[3]),float(center[4]))
            motion=motion_check(adjusted,center[7:9],initial_acceleration=acceleration)
            collision=collision_check(adjusted,float(center[6]),float(center[3]),float(center[4]),obstacles)
            deviation=float(np.linalg.norm(adjusted[1:]-raw['world_xy'][idx],axis=1).max())
            reasons=[]
            for condition,reason in [(route['matched'],'observed_start_road_route'),(body['passed'],'road_footprint'),
                                      (motion['passed'],'motion'),(collision['passed'],'constant_velocity_collision'),
                                      (not bad,'incomplete_obstacles'),(deviation<=1.,'refinement_deviation')]:
                if not condition:reasons.append(reason)
            proposed={**row,'route':route,'body':body,'motion':motion,'collision':collision,
                      'rejected_by':reasons,'passes_current_checks':not reasons,
                      'refinement':{'method':'quintic lateral tail shift after bounded smoothing',
                                    'tail_start_seconds':3.,'signed_shift_m':float(np.sign(requested)*amount),
                                    'normal':normal.tolist(),'max_deviation_from_raw_m':deviation,
                                    'max_allowed_deviation_m':1.,'within_deviation_bound':deviation<=1.,
                                    'scope':'New map-guided proposal; raw MTR score retained only as a source-candidate ranking heuristic.'}}
            matches=action_matches(proposed,action,conv['current_speed_mps'])
            trials.append({'candidate':row['candidate'],'action':action,'shift_m':float(np.sign(requested)*amount),
                           'max_deviation_from_raw_m':deviation,'rejected_by':reasons,'matches_action':matches})
            if not reasons and matches:
                report['candidates'][idx]=proposed;trajectories[idx]=adjusted[1:];modified.append(row['candidate']);break
    rows=report['candidates'];matching=[r for r in rows if r['passes_current_checks'] and action_matches(r,'lane_change_right',conv['current_speed_mps'])]
    selected=max(matching,key=lambda r:(r['score'],-r['candidate']))['candidate'] if matching else None
    report['summary'].update(run=str(output.relative_to(ROOT/'runs')),prediction_source='map_guided_tail_refinement_experiment',
                            passed_candidates=[r['candidate'] for r in rows if r['passes_current_checks']],
                            rejection_counts=dict(Counter(x for r in rows for x in r['rejected_by'])))
    report['map_tail_experiment']={'modified_candidates':modified,'trials':trials,'selected_right_merge_candidate':selected,
        'actions':list(actions),'matching_by_action':{action:[r['candidate'] for r in rows if r['passes_current_checks'] and action_matches(r,action,conv['current_speed_mps'])] for action in actions},
        'selection_scope':'Per-action final selection is evaluated by the persistent sequence planner; this metadata does not advance instruction stages.',
        'source_report_sha256':sha256(source/'anchored_feasibility.json'),
        'method_sha256':sha256(ROOT/'scripts/mtr_project/tail_refinement.py'),
        'source_arrays_sha256':{name:sha256(source/name) for name in ['internal_0000.npz','refined_v2_candidates.npz']},
        'source_code_sha256':{name:sha256(ROOT/'scripts'/name) for name in ['refine_connector_proposals.py','evaluate_candidate_checks.py','trajectory_checks.py','language_selector.py','mtr_project/connector_routes.py']},
        'scope':'Method designed after diagnosing doplan_006160. Further development diagnostics are not a blind test. Geometric connector assumption remains; lane-marking legality and closed-loop execution not established.'}
    output.mkdir(parents=True,exist_ok=True);shutil.copy2(source/'internal_0000.npz',output/'internal_0000.npz')
    np.savez_compressed(output/'refined_v2_candidates.npz',world_xy=trajectories,scores=raw['scores'])
    write_json(output/'anchored_feasibility.json',report)
    print(json.dumps(report['map_tail_experiment'],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--frame',type=int,default=975)
    parser.add_argument('--frames',type=int,nargs='+')
    parser.add_argument('--manifest');parser.add_argument('--source-tag',default='connector-route-v1')
    parser.add_argument('--output-tag',default='map-tail-v1')
    parser.add_argument('--actions',nargs='+',choices=['lane_change_left','lane_change_right'],default=['lane_change_right']);args=parser.parse_args()
    keys=[r['key'] for r in json.loads((ROOT/'runs'/checked_relative(args.manifest)).read_text())] if args.manifest else [f'doplan_006160-f{f:04d}' for f in args.frames or [args.frame]]
    for key in keys:refine_case(key,args.source_tag,args.output_tag,tuple(args.actions))
