"""Projection diagnostic only: compares raw-distorted and rectified image hypotheses."""
import json,sqlite3,pickle
import numpy as np
import cv2
from pyquaternion import Quaternion
from mtr_project.paths import ROOT
out=ROOT/'runs/project-v3/environment-grounding-v1';records=json.loads((out/'contexts.json').read_text());results=[]
for r in records:
 camera=next(x for x in r['camera_observations'] if x['channel']=='CAM_F0');frame=cv2.imread(str(out/f'video-{r["scene"]:02d}.jpg'))
 with sqlite3.connect((ROOT/r['source_db']).as_uri()+'?mode=ro',uri=True) as c:
  row=c.execute('SELECT e.x,e.y,e.z,e.qw,e.qx,e.qy,e.qz,cam.translation,cam.rotation,cam.intrinsic,cam.distortion,cam.width,cam.height FROM image i JOIN ego_pose e ON e.record_id=i.ego_pose_record_id JOIN camera cam ON cam.record_id=i.camera_record_id WHERE i.filename_jpg=?',(camera['filename'],)).fetchone()
  boxes=c.execute('SELECT hex(b.track_record_id),b.x,b.y,b.z FROM lidar_box b JOIN lidar_pc p ON p.record_id=b.lidar_pc_record_id WHERE p.timestamp=?',(r['timestamp_us'],)).fetchall()
 translation=np.array(pickle.loads(row[7]));rc=Quaternion(pickle.loads(row[8])).rotation_matrix;re=Quaternion(row[3:7]).rotation_matrix;origin=np.array(row[:3]);K=np.array(pickle.loads(row[9]),float);dist=np.array(pickle.loads(row[10]),float)
 candidates=[];panels=[]
 for name,d in [('Rectified hypothesis',np.zeros_like(dist)),('Raw-distorted hypothesis',dist)]:
  panel=frame.copy()
  for i,(track,x,y,z) in enumerate(boxes):
   pos=((np.array([x,y,z])-origin)@re-translation)@rc
   if pos[2]<1:continue
   px,_=cv2.projectPoints(pos.reshape(1,3),np.zeros(3),np.zeros(3),K,d);u,v=px.reshape(2)*np.array([frame.shape[1]/row[11],frame.shape[0]/row[12]])
   if 0<=u<frame.shape[1] and 0<=v<frame.shape[0]:
    cv2.circle(panel,(round(u),round(v)),5,(0,255,255),-1);cv2.putText(panel,track[:5],(round(u)+5,round(v)),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,0,255),1)
    candidates.append({'hypothesis':name,'track_id':track,'pixel':[float(u),float(v)],'depth_m':float(pos[2])})
  cv2.rectangle(panel,(0,0),(frame.shape[1],28),(255,255,255),-1);cv2.putText(panel,name+' - UNVERIFIED',(8,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),1);panels.append(panel)
 cv2.imwrite(str(out/f'projection-{r["scene"]:02d}.jpg'),np.vstack(panels));results.append({'scene':r['scene'],'camera_age_s':camera['age_s'],'status':'diagnostic_not_validated_correspondence','points':candidates})
 print('scene',r['scene'],'visible projected points',len(candidates))
(out/'projection-diagnostics.json').write_text(json.dumps(results,indent=2))
p=out/'index.html';s=p.read_text();s+='<article><h2>\u8f66\u8f86\u4f4d\u7f6e\u6295\u5f71\u6838\u5bf9：\u8fd8\u4e0d\u662f\u81ea\u52a8\u8bc6\u522b\u7ed3\u679c</h2><p>\u9ec4\u8272\u70b9\u662f\u628a\u6570\u636e\u5e93\u4e2d\u8f66\u8f86\u4e2d\u5fc3\u6295\u5f71\u5230\u89c6\u9891\u7684\u9884\u6d4b\u4f4d\u7f6e。\u4e0a\u4e0b\u4e24\u5f20\u5206\u522b\u5047\u8bbe\u89c6\u9891\u7ecf\u8fc7\u6216\u672a\u7ecf\u8fc7\u7578\u53d8\u6821\u6b63；\u5c1a\u672a\u9a8c\u8bc1\u89c6\u9891\u5b9e\u9645\u5904\u7406\u65b9\u5f0f。\u6570\u5b57\u662f\u8ddf\u8e2a\u7f16\u53f7\u7684\u4e00\u90e8\u5206，\u4e0d\u662f\u989c\u8272\u6216\u8f66\u578b\u8bc6\u522b。\u6295\u5f71\u5339\u914d\u901a\u8fc7\u540e，\u624d\u80fd\u628a\u89c6\u9891\u91cc\u8bc6\u522b\u51fa\u7684\u63cf\u8ff0\u7ed1\u5b9a\u5230\u5177\u4f53\u8f66\u8f86。</p>'
for r in records:s+=f'<h3>\u573a\u666f {r["scene"]:02d}</h3><img src="projection-{r["scene"]:02d}.jpg">'
p.write_text(s+'</article>',encoding='utf-8')
