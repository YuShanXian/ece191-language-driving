"""Evaluation-only audit: does the limited screen reject even the logged ego path?"""
import argparse,json,pickle
import numpy as np
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph,current_obstacles
from trajectory_checks import motion_check,collision_check

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',default='baseline-v1');p.add_argument('--split',default='development');args=p.parse_args()
    folder=ROOT/'runs/project-v2'/args.tag
    records=json.loads((folder/f'{args.split}-manifest.json').read_text());reports=[]
    for record in records:
        source=ROOT/'samples'/record['sample'];out=ROOT/'runs'/record['run']
        conv=json.loads((source/'conversion.json').read_text())
        with (source/conv['scenario']).open('rb') as stream:scene=pickle.load(stream)
        ego=scene['tracks']['ego']['state'];points=ego['position'][20:81,:2]
        graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map'])
        observed_history=graph.match(ego['position'][:21,:2],float(ego['heading'][0]))
        heading=float(ego['heading'][20]);length=float(ego['length'][20]);width=float(ego['width'][20])
        past_acceleration=np.diff(ego['velocity'][17:21],axis=0).mean(axis=0)/.1
        obstacles,bad=current_obstacles(conv)
        report={'key':record['key'],'source_clip':conv['source_clip'],'current_speed_mps':conv['current_speed_mps'],
                'history_matched':observed_history['matched'],
                'start_footprint':graph.body_check(points[:1],heading,length,width),
                'logged_route':graph.match(points,heading),
                'logged_body':graph.body_check(points,heading,length,width),
                'logged_motion':motion_check(points,ego['velocity'][20],initial_acceleration=past_acceleration),
                'logged_path_vs_constant_velocity_obstacles':collision_check(points,heading,length,width,obstacles),
                'invalid_obstacles':bad,
                'scope':'Evaluation-only future replay. A mismatch diagnoses model assumptions; it does not establish that a recorded driver was safe.'}
        reports.append(report)
        write_json(out/'screen-diagnostic.json',report)
        print(record['key'],'start',report['start_footprint']['passed'],'history',report['history_matched'],
              'logged body',report['logged_body']['passed'],'CV collision',report['logged_path_vs_constant_velocity_obstacles']['passed'],flush=True)
    write_json(folder/f'{args.split}-screen-diagnostics.json',reports)

if __name__=='__main__':main()
