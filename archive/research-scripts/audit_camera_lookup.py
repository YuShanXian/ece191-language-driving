"""Check whether SDK camera lookup omissions explain observed video frame counts."""
import bisect,csv,json,sqlite3,sys
from pathlib import Path
from mtr_project.paths import ROOT,sha256,write_json


def audit(clip):
    folder=ROOT/'data/doplan'/clip;dest=ROOT/'runs/project-v2/video-alignment'/clip
    with (folder/'gps.csv').open() as stream:gps=list(csv.DictReader(stream))
    with sqlite3.connect((ROOT/'data/nuplan/db'/f'{clip}.db').as_uri()+'?mode=ro',uri=True) as connection:
        images=connection.execute('SELECT img.timestamp,img.filename_jpg FROM image img JOIN camera cam ON cam.record_id=img.camera_record_id WHERE cam.channel=? ORDER BY img.timestamp',('CAM_F0',)).fetchall()
    image_times=[r[0] for r in images];missing=[];multiple=[];mapping=[]
    for index,row in enumerate(gps):
        timestamp=int(row['timestamp_us'])
        lo=bisect.bisect_left(image_times,timestamp-50000);hi=bisect.bisect_right(image_times,timestamp+50000)
        if lo==hi:missing.append({'gps_row_zero_based':index,'timestamp_us':timestamp,'source_iteration':int(row['frame'])});continue
        if hi-lo>1:multiple.append(index)
        mapping.append({'video_frame_if_source_contract_holds':len(mapping),'gps_row_zero_based':index,'timestamp_us':timestamp,
                        'camera_timestamp_candidates':[r[0] for r in images[lo:hi]]})
    video=next(r for r in json.loads((dest/'video-audit.json').read_text())['videos'] if r['file'].endswith('/F0.mp4'))
    sdk=Path(sys.prefix)/'lib/python3.10/site-packages/nuplan'
    result={'clip':clip,'gps_rows':len(gps),'front_video_decoded_frames':video['decoded_frame_count'],
            'sdk_default_camera_window_us':[-50000,50000],'missing_camera_lookup_rows':missing,
            'multiple_camera_matches_rows':multiple,'expected_written_frames_under_source_contract':len(mapping),
            'expected_count_matches_video':len(mapping)==video['decoded_frame_count'],
            'conditional_frame_mapping':mapping,
            'independent_raw_image_confirmation':False,
            'source_sha256':{'gps':sha256(folder/'gps.csv'),'video':video['sha256'],
                'exporter':sha256(ROOT/'runs/doplan-alignment/upstream-source/videoGPSGenerator.py'),
                'sdk_queries':sha256(sdk/'database/nuplan_db/nuplan_scenario_queries.py'),
                'sdk_scenario':sha256(sdk/'planning/scenario_builder/nuplan_db/nuplan_scenario.py')},
            'scope':'Predicts omission locations using inspected exporter and installed SDK behavior. A matching count supports this explanation but does not independently attest the video release generator version or compare decoded frames to raw sensor images.'}
    write_json(dest/'camera-lookup-audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['conditional_frame_mapping','source_sha256']},indent=2))


if __name__=='__main__':
    for clip in ['2021.06.09.12.39.51_veh-26_05332_05540','2021.06.09.18.23.43_veh-35_00026_00274']:audit(clip)
