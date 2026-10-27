"""Audit the new front video without assuming equal frame counts or exact offset."""
import csv,json,sqlite3
import cv2
import numpy as np
from pyproj import Transformer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mtr_project.paths import ROOT,write_json,sha256


def main():
    clip='2021.06.09.18.23.43_veh-35_00026_00274';folder=ROOT/'data/doplan'/clip
    dest=ROOT/'runs/project-v2/video-alignment'/clip;dest.mkdir(parents=True,exist_ok=True)
    with (folder/'gps.csv').open() as stream:rows=list(csv.DictReader(stream))
    times=np.asarray([int(r['timestamp_us']) for r in rows])
    if np.any(np.diff(times)<=0):raise ValueError('GPS times not strictly increasing')
    db=ROOT/'data/nuplan/db'/f'{clip}.db'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as connection:
        states=connection.execute('SELECT pc.timestamp,e.x,e.y,e.epsg FROM lidar_pc pc JOIN ego_pose e ON e.record_id=pc.ego_pose_record_id ORDER BY pc.timestamp').fetchall()
    lookup={r[0]:r for r in states};residuals=[]
    for row,timestamp in zip(rows,times):
        if int(timestamp) not in lookup:raise ValueError('GPS timestamp absent from its own database')
        state=lookup[int(timestamp)];transform=Transformer.from_crs(4326,int(state[3]),always_xy=True)
        xy=transform.transform(float(row['lon']),float(row['lat']));residuals.append(float(np.linalg.norm(np.asarray(xy)-state[1:3])))
    audit=json.loads((dest/'video-audit.json').read_text());video=audit['videos'][0]
    deficit=len(rows)-video['decoded_frame_count']
    report={'clip':clip,'gps_rows':len(rows),'front_video_decoded_frames':video['decoded_frame_count'],
            'exact_gps_database_matches':len(residuals),'maximum_position_residual_m':max(residuals),
            'front_video_frame_deficit':deficit,'frame_offset_status':'unresolved' if deficit else 'count_parity_only',
            'exact_video_to_gps_mapping_established':False,
            'hypothesis':'If the inspected exporter was used and the sole discrepancy is one omitted camera frame, video frame j corresponds to GPS row j or j+1. The omission location is unknown.',
            'source_sha256':{'gps':sha256(folder/'gps.csv'),'video':sha256(folder/'F0.mp4'),'database':sha256(db)},
            'review_frames':[]}
    capture=cv2.VideoCapture(str(folder/'F0.mp4'));fig,axes=plt.subplots(2,2,figsize=(16,10.7))
    for ax,second in zip(axes.flat,[152.,155.,158.,161.]):
        target=states[0][0]+int(second*1e6);index=int(np.argmin(abs(times-target)))
        index=min(index,video['decoded_frame_count']-1)
        capture.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=capture.read()
        if not ok:raise ValueError('Cannot read review frame')
        bounds=[(int(times[index])-states[0][0])/1e6,(int(times[min(index+max(deficit,0),len(times)-1)])-states[0][0])/1e6]
        ax.imshow(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));ax.axis('off')
        ax.set_title(f'Video frame {index} | conditional DB time {bounds[0]:.1f}–{bounds[1]:.1f} s',fontsize=11)
        report['review_frames'].append({'video_frame':index,'conditional_database_time_range_sec':bounds})
    capture.release();fig.suptitle('Qualitative review of the newly detected left merge — exact camera/GPS offset unresolved',fontsize=15)
    fig.text(.02,.012,'GPS has 1,235 rows, front video has 1,234 frames. Time ranges assume a single omitted camera frame; they are not independent synchronization proof.',fontsize=10)
    fig.subplots_adjust(left=.025,right=.975,top=.91,bottom=.06,hspace=.18,wspace=.06)
    fig.savefig(dest/'left-merge-review.png',dpi=140);plt.close(fig)
    write_json(dest/'alignment-audit.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
