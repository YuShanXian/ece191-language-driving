"""Decode downloaded videos and compare counts with the ordered GPS rows."""
import argparse,csv,json,re
import cv2
from mtr_project.paths import ROOT,write_json,sha256

def main():
    p=argparse.ArgumentParser();p.add_argument('--clip',default='2021.06.09.12.39.51_veh-26_05332_05540');args=p.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+',args.clip) or '..' in args.clip:raise ValueError('Invalid clip name')
    folder=ROOT/'data/doplan'/args.clip
    gps=folder/'gps.csv'
    if not gps.exists():raise FileNotFoundError('This clip needs its own GPS file: '+str(gps))
    with gps.open() as stream:rows=list(csv.DictReader(stream))
    results=[];dest=ROOT/'runs/project-v2/video-alignment'/args.clip;dest.mkdir(parents=True,exist_ok=True)
    files=sorted(folder.glob('*.mp4'))
    if not files:raise ValueError('No videos downloaded for this clip')
    for file in files:
        capture=cv2.VideoCapture(str(file))
        if not capture.isOpened():raise ValueError('Cannot open '+str(file))
        metadata_count=int(capture.get(cv2.CAP_PROP_FRAME_COUNT));fps=capture.get(cv2.CAP_PROP_FPS);count=0
        chosen={0,metadata_count//2,metadata_count-1};frame_paths=[]
        while True:
            ok,frame=capture.read()
            if not ok:break
            if count in chosen:
                name=f'{file.stem}-frame-{count:05d}.png';cv2.imwrite(str(dest/name),frame);frame_paths.append(name)
            count+=1
        capture.release()
        result={'file':str(file.relative_to(ROOT)),'sha256':sha256(file),'bytes':file.stat().st_size,
                'metadata_frame_count':metadata_count,'decoded_frame_count':count,'playback_fps':fps,
                'playback_duration_sec':count/fps if fps else None,'gps_rows':len(rows),'frame_count_equals_gps_rows':count==len(rows),
                'gps_duration_sec':(int(rows[-1]['timestamp_us'])-int(rows[0]['timestamp_us']))/1e6,'sample_frame_images':frame_paths}
        results.append(result);print(json.dumps(result),flush=True)
    report={'clip':args.clip,'gps_file':str(gps.relative_to(ROOT)),'gps_sha256':sha256(gps),'videos':results,
            'scope':'Equal counts support frame parity but do not independently prove each image-to-timestamp correspondence. Inspect generator and sample frames; playback FPS must not substitute for GPS timestamps.'}
    write_json(dest/'video-audit.json',report)

if __name__=='__main__':main()
