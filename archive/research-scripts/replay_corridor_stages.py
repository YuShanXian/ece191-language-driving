"""Compare connector-aware observations on an existing recorded-pose replay."""
import argparse,json,re,sqlite3
from collections import Counter
import numpy as np
from nuplan.database.nuplan_db.nuplan_scenario_queries import get_ego_state_for_lidarpc_record_id_from_db
from evaluate_candidate_checks import load_graph
from mtr_project.paths import ROOT,write_json,sha256
from mtr_project.observations import MeasuredState
from mtr_project.corridor_observer import CorridorManeuverObserver,corridor_contains_body
from mtr_project.language import parse_instruction
from mtr_project.stages import StageMachine


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',default='doplan_006160-window-v2')
    parser.add_argument('--tag',default='corridor-v1');args=parser.parse_args()
    if not all(re.fullmatch(r'[a-zA-Z0-9_-]+',x) for x in [args.source,args.tag]):raise ValueError('Simple replay names required')
    source=ROOT/'runs/project-v2/replay'/f'{args.source}.json';value=json.loads(source.read_text())
    output=source.with_name(args.source+'-'+args.tag+'.json')
    if output.exists():raise ValueError('Preserve earlier experimental replay')
    db=ROOT/'data/nuplan/db'/f'{value["source_clip"]}.db'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as connection:
        record_id,epsg=connection.execute('SELECT pc.record_id,e.epsg FROM lidar_pc pc JOIN ego_pose e ON e.record_id=pc.ego_pose_record_id WHERE pc.timestamp=?',
                                     (value['trace'][0]['timestamp_us'],)).fetchone()
    initial=get_ego_state_for_lidarpc_record_id_from_db(str(db),record_id.hex())
    length=initial.car_footprint.length;width=initial.car_footprint.width
    detector=CorridorManeuverObserver();machine=StageMachine(parse_instruction(value['instruction']))
    tiles={};trace=[]
    for original in value['trace']:
        xy=np.asarray(original['xy']);tile=tuple(np.floor(xy/250).astype(int));origin=(np.array(tile)+.5)*250
        if tile not in tiles:tiles[tile]=load_graph(origin,epsg)
        graph=tiles[tile];local=original['localization']
        state=MeasuredState(original['timestamp_us']/1e6,float(xy[0]),float(xy[1]),original['heading'],original['speed_mps'],
                            local['node'],local.get('node_kind'),local['body_inside_node'])
        contains=lambda node:corridor_contains_body(graph,node,xy-origin,state.heading,length,width)
        observed=detector.update(state,graph.edges,{k:n.kind for k,n in graph.nodes.items()},contains)
        trace.append({**original,'baseline_observed_actions':original['observed_actions'],
                      'observed_actions':list(observed.completed_actions),'stage':machine.update(observed)})
    result={**value,'trace':trace,'observed_action_counts':dict(Counter(a for r in trace for a in r['observed_actions'])),
            'final_stage':machine.snapshot(),'observer':'connector_corridor_experiment_v1',
            'observer_evidence':detector.evidence,'comparison_source':str(source.relative_to(ROOT)),
            'comparison_source_sha256':sha256(source),
            'observer_source_sha256':sha256(ROOT/'scripts/mtr_project/corridor_observer.py'),
            'observer_configuration':{'settle_seconds':.5,'max_unknown_seconds':1.,'maximum_observation_gap_seconds':.3,
                                      'corridor_extension_m':12.},
            'scope':'Exploratory observer designed after inspecting doplan_006160; additional development recordings are diagnostic comparisons. No independent accuracy claim, no actuation; frozen candidate-selection baseline unchanged.'}
    write_json(output,result)
    print(json.dumps({k:result[k] for k in ['observer','observed_action_counts','final_stage','observer_evidence','scope']},indent=2))


if __name__=='__main__':main()
