"""Advance instruction stages from recorded poses; never simulate the selected path."""
import argparse
import json
import sqlite3
from collections import Counter
import numpy as np
from nuplan.database.nuplan_db.nuplan_scenario_queries import get_ego_state_for_lidarpc_record_id_from_db
from evaluate_candidate_checks import load_graph
from mtr_project.paths import ROOT, write_json
from mtr_project.localization import locate_pose
from mtr_project.observations import MeasuredState, ManeuverObserver
from mtr_project.language import parse_instruction
from mtr_project.stages import StageMachine
from mtr_project.timing import interval_bounds, within_interval


def replay(db, instruction, start_seconds=0., duration=None, stride=2):
    if not isinstance(stride,int) or stride<1:raise ValueError('Positive observation stride required')
    program = parse_instruction(instruction)
    if program['status']!='parsed':raise ValueError('Instruction is outside the controlled grammar')
    machine = StageMachine(program)
    with sqlite3.connect(db.as_uri()+'?mode=ro', uri=True) as connection:
        frames = connection.execute('SELECT pc.record_id,pc.timestamp,e.epsg FROM lidar_pc pc JOIN ego_pose e ON pc.ego_pose_record_id=e.record_id ORDER BY pc.timestamp').fetchall()[::stride]
    first_time = frames[0][1]
    bounds = interval_bounds(first_time, start_seconds, duration)
    frames = [r for r in frames if within_interval(r[1], bounds)]
    if not frames:raise ValueError('No observations in requested interval')
    observer = ManeuverObserver({}); tiles = {}; previous_node = None; traces = []; reasons=Counter()
    for record_id, timestamp, epsg in frames:
        ego = get_ego_state_for_lidarpc_record_id_from_db(str(db), record_id.hex())
        xy = np.array([ego.center.x, ego.center.y]); tile=tuple(np.floor(xy/250).astype(int))
        origin=(np.array(tile)+.5)*250
        if tile not in tiles:tiles[tile]=load_graph(origin, epsg)
        graph=tiles[tile];observer.edges.update(graph.edges)
        pose=locate_pose(graph, xy-origin, ego.center.heading, ego.car_footprint.length,
                         ego.car_footprint.width, previous_node)
        previous_node=pose['node'];reasons[pose['reason']]+=1
        state=MeasuredState(timestamp/1e6,float(xy[0]),float(xy[1]),ego.center.heading,
                            ego.dynamic_car_state.speed,pose['node'],pose.get('node_kind'),pose['body_inside_node'])
        observed=observer.update(state);stage=machine.update(observed)
        traces.append({'seconds_from_first_lidar':(timestamp-first_time)/1e6,'timestamp_us':timestamp,
                       'xy':xy.tolist(),'heading':ego.center.heading,'speed_mps':ego.dynamic_car_state.speed,
                       'localization':pose,'observed_actions':list(observed.completed_actions),'stage':stage})
    return {'source_clip':db.stem,'instruction':instruction,'program':program,'frames':len(traces),
            'requested_interval_us':list(bounds),'interval_convention':'[start,end)','observation_stride':stride,
            'localization_counts':dict(reasons),'observed_action_counts':dict(Counter(a for t in traces for a in t['observed_actions'])),
            'final_stage':machine.snapshot(),'trace':traces,
            'scope':'Recorded-driver replay only. No selected MTR trajectory is executed. Stage completion is causal measured-state evidence, not language compliance or closed-loop control.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--instruction',required=True)
    p.add_argument('--start-seconds',type=float,default=0);p.add_argument('--duration',type=float)
    p.add_argument('--stride',type=int,default=2)
    p.add_argument('--output',required=True);args=p.parse_args()
    db=(ROOT/args.db).resolve();out=(ROOT/args.output).resolve()
    if not db.is_relative_to(ROOT) or not out.is_relative_to(ROOT):raise ValueError('Paths must remain in project')
    if out.exists():raise ValueError('Choose a new output; preserve previous replay')
    report=replay(db,args.instruction,args.start_seconds,args.duration,args.stride);write_json(out,report)
    print(json.dumps({k:v for k,v in report.items() if k!='trace'},indent=2))

if __name__=='__main__':main()
