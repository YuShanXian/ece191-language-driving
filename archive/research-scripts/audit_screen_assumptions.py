"""Evaluation-only road coverage and obstacle extrapolation diagnostics."""
import argparse,json,pickle,sqlite3
from collections import Counter
import numpy as np
from shapely.geometry import mapping
from evaluate_candidate_checks import load_graph,current_obstacles
from trajectory_checks import footprint,headings
from mtr_project.paths import ROOT,write_json
from mtr_project.sources import source_database


def audit(record):
    folder=ROOT/'samples'/record['sample'];out=ROOT/'runs'/record['run']
    conversion=json.loads((folder/'conversion.json').read_text())
    with (folder/conversion['scenario']).open('rb') as stream:scene=pickle.load(stream)
    ego=scene['tracks']['ego']['state'];xy=ego['position'][20:81,:2]
    graph=load_graph(np.asarray(conversion['origin_xy_m']),conversion['source_epsg'],conversion['source_map'])
    body=footprint(xy[0],float(ego['heading'][20]),float(ego['length'][20]),float(ego['width'][20]))
    outside=body.difference(graph.surface)
    diagnostic=json.loads((out/'screen-diagnostic.json').read_text())
    hits=diagnostic['logged_path_vs_constant_velocity_obstacles']['first_hits']
    objects,bad=current_obstacles(conversion);lookup={o['id']:o for o in objects}
    connection=sqlite3.connect(source_database(conversion).as_uri()+'?mode=ro',uri=True)
    origin=np.asarray(conversion['origin_xy_m']);hit_reports=[]
    for hit in hits:
        obj=lookup[hit['object_id']];timestamp=conversion['current_timestamp_us']+round(hit['time_sec']*1e6)
        row=connection.execute('''SELECT pc.timestamp,b.x,b.y,b.yaw,b.length,b.width FROM lidar_box b JOIN lidar_pc pc ON b.lidar_pc_record_id=pc.record_id
            WHERE b.track_record_id=? AND pc.timestamp BETWEEN ? AND ? ORDER BY ABS(pc.timestamp-?) LIMIT 1''',
            (bytes.fromhex(obj['id']),timestamp-30000,timestamp+30000,timestamp)).fetchone()
        predicted=np.asarray(obj['xy'])+np.asarray(obj['velocity'])*hit['time_sec']
        report={'hit':hit,'assumed_position':predicted.tolist(),'observed_future_available':row is not None}
        if row is not None:
            actual=np.asarray(row[1:3])-origin
            step=hit['time_sec']/.1;lo=int(np.floor(step));hi=int(np.ceil(step));fraction=step-lo
            ego_xy=xy[lo]*(1-fraction)+xy[hi]*fraction
            # Use recorded heading here, not the candidate tangent estimate.
            theta=float(ego['heading'][20+lo]);delta=np.arctan2(np.sin(ego['heading'][20+hi]-theta),np.cos(ego['heading'][20+hi]-theta))
            ego_body=footprint(ego_xy,theta+fraction*delta,float(ego['length'][20]),float(ego['width'][20]),.2)
            report.update({'observed_position':actual.tolist(),'extrapolation_error_m':float(np.linalg.norm(actual-predicted)),
                           'actual_timestamp_error_us':int(row[0]-timestamp),
                           'recorded_boxes_overlap_at_hit':ego_body.intersects(footprint(actual,row[3],row[4],row[5],.2))})
        hit_reports.append(report)
    connection.close()
    return {'scene':record['key'],'start_footprint_area_m2':body.area,'outside_road_area_m2':outside.area,
            'outside_fraction':outside.area/body.area,'outside_geometry':mapping(outside),
            'logged_body_failed':not diagnostic['logged_body']['passed'],
            'cv_first_hit_audit':hit_reports,
            'scope':'Future observations are used only to audit a forecast assumption after selection. No screen threshold is changed.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',default='baseline-v1');p.add_argument('--split',default='development');args=p.parse_args()
    folder=ROOT/'runs/project-v2'/args.tag
    records=json.loads((folder/f'{args.split}-manifest.json').read_text());reports=[audit(r) for r in records]
    write_json(folder/f'{args.split}-assumption-audit.json',reports)
    for r in reports:print(r['scene'],'start outside m2',round(r['outside_road_area_m2'],3),'CV hits',r['cv_first_hit_audit'])

if __name__=='__main__':main()
