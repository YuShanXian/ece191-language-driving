"""Evidence for one doPlan clip's frame/GPS/DB mapping, with explicit limits."""
import csv,json,sqlite3
import numpy as np
from pyproj import Transformer
from mtr_project.paths import ROOT,write_json,sha256
from mtr_project.annotations import load_release,align_to_gps

def main():
    clip='2021.06.09.12.39.51_veh-26_05332_05540';folder=ROOT/'data/doplan'/clip;gps=folder/'gps.csv'
    with gps.open() as stream:rows=list(csv.DictReader(stream))
    db=ROOT/'data/nuplan/db'/f'{clip}.db'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as connection:
        observed=connection.execute('''SELECT pc.timestamp,pc.record_id,e.x,e.y,e.epsg FROM lidar_pc pc
            JOIN ego_pose e ON pc.ego_pose_record_id=e.record_id ORDER BY pc.timestamp''').fetchall()
    lookup={r[0]:(i,r) for i,r in enumerate(observed)};mappings=[];residuals=[]
    for index,row in enumerate(rows):
        timestamp=int(row['timestamp_us'])
        if timestamp not in lookup:raise ValueError('GPS timestamp missing in exact DB')
        lidar_index,state=lookup[timestamp]
        x,y=Transformer.from_crs(4326,int(state[4]),always_xy=True).transform(float(row['lon']),float(row['lat']))
        error=float(np.hypot(x-state[2],y-state[3]));residuals.append(error)
        mappings.append({'video_frame_zero_based':index,'gps_source_iteration':int(row['frame']),
                         'timestamp_us':timestamp,'ego_xy_m':[state[2],state[3]],'lidar_index':lidar_index,'lidar_record_id':state[1].hex(),'gps_db_position_residual_m':error})
    audit=json.loads((ROOT/'runs/project-v2/video-alignment'/clip/'video-audit.json').read_text())
    expected={'F0','B0','L0','L1','L2','R0','R1','R2','gps_map'}
    names={r['file'].split('/')[-1].removesuffix('.mp4') for r in audit['videos']}
    parity=names==expected and all(v['frame_count_equals_gps_rows'] for v in audit['videos'])
    labels,source=load_release(ROOT/'references/release_annotationsV1.csv')
    aligned=[]
    for label in labels:
        if label.clip_id!=clip:continue
        result=align_to_gps(label,gps,lookup,video_frames_verified=False)
        result['video_count_parity_observed']=parity
        result['window_mapping_support']='source_contract_plus_decoded_counts_and_exact_GPS_DB_matches' if parity else 'incomplete'
        result['usable_for_window_level_exploration']=parity and result['status']=='conditional_on_video_frame_parity'
        # No instruction utterance/onset or counterfactual success truth is created.
        result['usable_for_action_onset_or_compliance_evaluation']=False
        aligned.append(result)
    source_dir=ROOT/'runs/doplan-alignment/upstream-source'
    report={'clip':clip,'gps_rows':len(rows),'all_nine_videos_match_row_count':parity,
            'maximum_gps_db_position_residual_m':max(residuals),'gps_db_exact_timestamp_matches':len(mappings),
            'annotation_interval_convention':'zero-based [start,end), based on random_segment, set_segment_start_frame and write_label_row in inspected labeler',
            'source_contract':'Exporter writes a GPS row once per successful iteration, then at most one image per camera. All cameras matching the GPS row count supports no per-camera missing append for this clip.',
            'evidence_files':{'gps':sha256(gps),'database':sha256(db),**{name:sha256(source_dir/name) for name in ['videoGPSGenerator.py','userLabeler.py','GPSgenerator.py']}},
            'frame_mapping':mappings,'annotations':aligned,
            'remaining_limits':['Exact exporter version used for this April video release is not independently attested.',
                                'No raw-camera image hash comparison; sensor acquisition latency not measured.',
                                'Label interval describes a video window, not when a passenger spoke or when an action began.',
                                'Current release duration uses 5 samples/s; video file playback uses 20 frames/s. Use GPS timestamps.']}
    write_json(ROOT/'runs/project-v2/video-alignment'/clip/'alignment-evidence.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('frame_mapping','annotations')},indent=2))
    print('Labels:',[(r['annotation']['annotation_id'],r['annotation']['instruction'],r['usable_for_window_level_exploration']) for r in aligned])

if __name__=='__main__':main()
