"""Build source-pinned, explicitly conditional mappings for downloaded clips."""
import csv,json,sqlite3
from pyproj import Transformer
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.annotations import load_release
from mtr_project.video_alignment import validate_camera_mapping,annotation_window


def main():
    release=ROOT/'references/release_annotationsV1.csv';labels,_=load_release(release)
    for clip in ['2021.06.09.12.39.51_veh-26_05332_05540','2021.06.09.18.23.43_veh-35_00026_00274']:
        folder=ROOT/'runs/project-v2/video-alignment'/clip;camera_path=folder/'camera-lookup-audit.json'
        audit=json.loads(camera_path.read_text());gps_path=ROOT/'data/doplan'/clip/'gps.csv'
        if sha256(gps_path)!=audit['source_sha256']['gps']:raise ValueError('GPS changed since camera audit')
        videos=json.loads((folder/'video-audit.json').read_text())['videos']
        for video in videos:
            if sha256(ROOT/video['file'])!=video['sha256']:raise ValueError('Video changed since decode audit')
        front=next(v for v in videos if v['file'].endswith('/F0.mp4'))
        if front['sha256']!=audit['source_sha256']['video']:raise ValueError('Camera audit refers to another video')
        with gps_path.open() as stream:gps=list(csv.DictReader(stream))
        times=[int(r['timestamp_us']) for r in gps];conditional=validate_camera_mapping(audit,times)
        db=ROOT/'data/nuplan/db'/f'{clip}.db'
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as connection:
            states=connection.execute('SELECT pc.timestamp,pc.record_id,e.x,e.y,e.epsg FROM lidar_pc pc JOIN ego_pose e ON e.record_id=pc.ego_pose_record_id ORDER BY pc.timestamp').fetchall()
        lookup={r[0]:(i,r) for i,r in enumerate(states)};gps_mapping=[];projectors={}
        for index,row in enumerate(gps):
            timestamp=times[index];lidar_index,state=lookup[timestamp]
            if state[4] not in projectors:projectors[state[4]]=Transformer.from_crs(4326,int(state[4]),always_xy=True)
            x,y=projectors[state[4]].transform(float(row['lon']),float(row['lat']))
            error=((x-state[2])**2+(y-state[3])**2)**.5
            if error>.01:raise ValueError('GPS and database positions disagree')
            gps_mapping.append({'gps_row_zero_based':index,'gps_source_iteration':int(row['frame']),
                'timestamp_us':timestamp,'ego_xy_m':[state[2],state[3]],'lidar_index':lidar_index,
                'lidar_record_id':state[1].hex(),'gps_db_position_residual_m':error})
        mapping=[{**gps_mapping[r['gps_row_zero_based']],'video_frame_zero_based':i} for i,r in enumerate(conditional)]
        # Other original-clip cameras are eligible only when decoded counts match F0.
        compatible=[v for v in videos if v['decoded_frame_count']==len(mapping)]
        result={'clip':clip,'schema':'conditional_camera_lookup_v1','gps_rows':len(gps),
            'video_frames':len(mapping),'videos':compatible,'frame_mapping':mapping,
            'missing_camera_gps_rows':[r['gps_row_zero_based'] for r in audit['missing_camera_lookup_rows']],
            'maximum_gps_db_position_residual_m':max(r['gps_db_position_residual_m'] for r in gps_mapping),
            'annotations':[annotation_window(label,mapping,times) for label in labels if label.clip_id==clip],
            'source_sha256':{'camera_audit':sha256(camera_path),'video_audit':sha256(folder/'video-audit.json'),
                'gps':sha256(gps_path),'database':sha256(db),'release':sha256(release),'generator':sha256(__file__),
                'mapping_code':sha256(ROOT/'scripts/mtr_project/video_alignment.py')},
            'remaining_limits':['Source-contract inference, not independently accessenticated raw-image alignment.',
                'Release exporter version unconfirmed; multiple-camera lookup ambiguities rejected.',
                'Annotation window start is not known passenger instruction time. No compliance ground truth.']}
        output=folder/'viewer-alignment.json'
        if output.exists() and json.loads(output.read_text())!=result:raise ValueError('Preserve earlier mapping; version changed evidence separately')
        write_json(output,result)
        print(json.dumps({'clip':clip,'frames':len(mapping),'gps_rows':len(gps),'lidar_index_parities':sorted({r['lidar_index']%2 for r in mapping}),
            'annotations':[(a['annotation']['annotation_id'],a['usable_for_window_level_exploration']) for a in result['annotations']]}))


if __name__=='__main__':main()
