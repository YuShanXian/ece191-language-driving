"""Attach three downloaded camera clips using the existing conditional alignment audit."""
import csv,json,sqlite3,subprocess,sys
from pathlib import Path
from mtr_project.paths import ROOT,write_json
from mtr_project.video_alignment import validate_camera_mapping
from audit_camera_lookup import audit
from pyproj import Transformer
clips=['2021.06.14.18.42.45_veh-12_01065_01152','2021.06.23.15.18.10_veh-26_00016_00143','2021.07.16.21.17.55_veh-26_03772_03842']
for clip in clips:
 subprocess.run([sys.executable,str(ROOT/'scripts/audit_doplan_video.py'),'--clip',clip],check=True)
 audit(clip)
 dest=ROOT/'runs/project-v2/video-alignment'/clip
 a=json.loads((dest/'camera-lookup-audit.json').read_text())
 with (ROOT/'data/doplan'/clip/'gps.csv').open() as f:gps=list(csv.DictReader(f))
 times=[int(r['timestamp_us']) for r in gps]
 mapping=validate_camera_mapping(a,times)
 with sqlite3.connect((ROOT/'data/nuplan/db'/f'{clip}.db').as_uri()+'?mode=ro',uri=True) as db:
  states=db.execute('SELECT pc.timestamp,e.x,e.y,e.epsg FROM lidar_pc pc JOIN ego_pose e ON e.record_id=pc.ego_pose_record_id').fetchall()
 lookup={r[0]:r for r in states};residuals=[];projectors={}
 for row,t in zip(gps,times):
  state=lookup[t];epsg=state[3]
  if epsg not in projectors:projectors[epsg]=Transformer.from_crs(4326,int(epsg),always_xy=True)
  x,y=projectors[epsg].transform(float(row['lon']),float(row['lat']))
  residuals.append(((x-state[1])**2+(y-state[2])**2)**.5)
 if max(residuals)>.01:raise ValueError('GPS does not match database')
 videos=json.loads((dest/'video-audit.json').read_text())['videos']
 result={'clip':clip,'schema':'conditional_camera_lookup_v1','gps_rows':len(gps),'video_frames':len(mapping),
 'videos':[v for v in videos if v['decoded_frame_count']==len(mapping)],
 'frame_mapping':[{'timestamp_us':r['timestamp_us'],'gps_row_zero_based':r['gps_row_zero_based'],'video_frame_zero_based':i} for i,r in enumerate(mapping)],
 'maximum_gps_db_position_residual_m':max(residuals),
 'remaining_limits':['Conditional on inspected exporter and SDK lookup; not independent raw-image accessentication.']}
 write_json(dest/'viewer-alignment.json',result)
 print('ALIGNED',clip,len(mapping),max(residuals),flush=True)
subprocess.run([sys.executable,str(ROOT/'scripts/prepare_human_camera_view.py')],check=True)
