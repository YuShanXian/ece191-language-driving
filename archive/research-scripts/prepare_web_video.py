"""Make a browser copy, preserving all decoded frames and playback timing."""
import json
import subprocess
from pathlib import Path
import cv2
import imageio_ffmpeg
import numpy as np
from mtr_project.paths import ROOT, sha256, write_json


def main():
    clip='2021.06.09.12.39.51_veh-26_05332_05540'
    source=ROOT/'data/doplan'/clip/'gps_map.mp4'
    folder=ROOT/'runs/project-v2/web-video'/clip
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/source.name
    if target.exists():raise ValueError('Preserve the existing converted video')
    temporary=folder/'gps_map.partial.mp4'
    executable=imageio_ffmpeg.get_ffmpeg_exe()
    command=[executable,'-nostdin','-n','-i',str(source),'-map','0:v:0','-an',
             '-c:v','libx264','-crf','18','-preset','fast','-threads','2',
             '-pix_fmt','yuv420p','-fps_mode','passthrough','-movflags','+faststart',str(temporary)]
    result=subprocess.run(command,capture_output=True,text=True)
    (folder/'conversion.log').write_text(result.stderr,encoding='utf-8')
    result.check_returncode()
    original=cv2.VideoCapture(str(source));derived=cv2.VideoCapture(str(temporary))
    fps_original=original.get(cv2.CAP_PROP_FPS);fps_derived=derived.get(cv2.CAP_PROP_FPS)
    frames=0;maximum_mae=0.;time_difference=0.
    while True:
        ok_a,a=original.read();ok_b,b=derived.read()
        if ok_a!=ok_b:raise ValueError('Frame count changed during conversion')
        if not ok_a:break
        if a.shape!=b.shape:raise ValueError('Frame dimensions changed')
        error=float(np.abs(a.astype(np.int16)-b.astype(np.int16)).mean())
        maximum_mae=max(maximum_mae,error)
        time_difference=max(time_difference,abs(original.get(cv2.CAP_PROP_POS_MSEC)-derived.get(cv2.CAP_PROP_POS_MSEC)))
        frames+=1
    original.release();derived.release()
    if frames!=1035 or abs(fps_original-fps_derived)>1e-6 or time_difference>.1 or maximum_mae>8:
        raise ValueError('Converted video failed frame/timing/image correspondence check')
    temporary.rename(target)
    receipt={'source':str(source.relative_to(ROOT)),'source_sha256':sha256(source),
             'derived':str(target.relative_to(ROOT)),'derived_sha256':sha256(target),
             'derived_bytes':target.stat().st_size,'frames_checked_in_order':frames,
             'fps':fps_derived,'maximum_frame_timestamp_difference_ms':time_difference,
             'maximum_mean_absolute_pixel_difference':maximum_mae,
             'conversion':'H.264 lossy browser copy, all frames retained; original file unchanged',
             'imageio_ffmpeg_version':imageio_ffmpeg.__version__,
             'ffmpeg_version':imageio_ffmpeg.get_ffmpeg_version(),'command':command,
             'script_sha256':sha256(Path(__file__))}
    write_json(folder/'conversion-receipt.json',receipt)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
