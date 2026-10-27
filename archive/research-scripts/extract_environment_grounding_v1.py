"""Extract exact-anchor observations; no future states used for grounding."""
import json,sqlite3,csv,html
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mtr_project.paths import ROOT
from mtr_project.traffic_context import signal_observations
from audit_traffic_context import connector_map
from evaluate_candidate_checks import load_graph
from automatic_road_selector import select_road

def extract(w):
 c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());timestamp=c['current_timestamp_us'];db=ROOT/c['source_db']
 center=np.load(ROOT/'runs'/w['run']/'internal_0000.npz')['center'].astype(float);h=center[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]])
 graph=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);mapcontext=connector_map(ROOT/c['source_map'])
 with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
  pc=conn.execute('SELECT record_id FROM lidar_pc WHERE timestamp=?',(timestamp,)).fetchall();assert len(pc)==1;record_id=pc[0][0]
  obs=signal_observations(conn.execute('SELECT lane_connector_id,status FROM traffic_light_status WHERE lidar_pc_record_id=?',(record_id,)).fetchall())
  objs=conn.execute('SELECT hex(b.track_record_id),c.name,b.x,b.y,b.vx,b.vy,b.width,b.length FROM lidar_box b JOIN track t ON t.record_id=b.track_record_id JOIN category c ON c.record_id=t.category_record_id WHERE b.lidar_pc_record_id=?',(record_id,)).fetchall()
  cameras=conn.execute('SELECT c.channel,i.timestamp,i.filename_jpg,c.width,c.height FROM camera c JOIN image i ON i.camera_record_id=c.record_id WHERE i.timestamp=(SELECT MAX(i2.timestamp) FROM image i2 WHERE i2.camera_record_id=c.record_id AND i2.timestamp<=?)',(timestamp,)).fetchall()
 objects=[]
 for track,kind,x,y,vx,vy,width,length in objs:
  xy=(np.array([x,y])-np.asarray(c['origin_xy_m'])-center[:2])@rot
  objects.append({'track_id':track,'category':kind,'xy_forward_left_m':xy.tolist(),'velocity_forward_left_mps':(np.array([vx or 0,vy or 0])@rot).tolist(),'width_m':width,'length_m':length,'color':None,'vehicle_subtype':None})
 routes=[]
 for text in ['Go straight','Turn left','Turn right']:
  road=select_road(graph,center,text)
  if road.get('status')!='selected':routes.append({'instruction':text,'status':road['status']});continue
  connectors=[k[1:] for k in road['selected']['path'] if k.startswith('C')]
  routes.append({'instruction':text,'selection_reason':road['reason'],'path':road['selected']['path'],'connectors':[{'id':k,'signal':obs.get(k,{'classification':'unobserved'}),'stop_regions':mapcontext.get(k,{}).get('raw_stop_region_associations',[])} for k in connectors]})
 clip=c['source_clip'];gps=list(csv.DictReader((ROOT/'data/doplan'/clip/'gps.csv').open()));row=min(range(len(gps)),key=lambda i:abs(int(gps[i]['timestamp_us'])-timestamp))
 align=ROOT/'runs/project-v2/video-alignment'/clip/'viewer-alignment.json';video_info={'path':str(ROOT/'data/doplan'/clip/'F0.mp4'),'nearest_gps_row':row,'gps_time_residual_s':abs(int(gps[row]['timestamp_us'])-timestamp)/1e6,'mapping_status':'unverified_frame_equals_gps_row','video_frame':row}
 if align.exists():
  a=json.loads(align.read_text());match=[x for x in a['frame_mapping'] if x['gps_row_zero_based']==row]
  if len(match)==1:video_info.update(mapping_status='conditional_camera_lookup',video_frame=match[0]['video_frame_zero_based'])
 return {'scene':w['scene'],'timestamp_us':timestamp,'source_db':c['source_db'],'signals':obs,'objects':objects,'routes':routes,'camera_observations':[{'channel':a,'timestamp_us':b,'age_s':(timestamp-b)/1e6,'filename':f,'size':[ww,hh]} for a,b,f,ww,hh in cameras],'video':video_info,'scope':'Exact anchor observations only; signal state does not establish a future green transition. Color, SUV subtype and building identity are not grounded.'},graph,center,rot

def main():
 out=ROOT/'runs/project-v3/environment-grounding-v1';out.mkdir(exist_ok=True);manifest=json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text());records=[]
 page='''<!doctype html><meta charset="utf-8"><title>\u73af\u5883\u4fe1\u606f\u6838\u5bf9</title><style>body{max-width:1250px;margin:35px auto;font:20px Segoe UI;background:#f5f8fb;color:#153249}article{background:white;padding:28px;margin:30px 0;border-radius:14px}img{width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}small{color:#647789}</style><h1>\u4ece nuPlan \u81ea\u52a8\u8bfb\u53d6\u73af\u5883\u4fe1\u606f</h1><p>\u7070\u7ebf\u662f\u5730\u56fe\u4e2d\u5fc3\u7ebf；\u5706\u70b9\u662f\u6570\u636e\u5e93\u5728\u5f53\u524d\u65f6\u523b\u8bb0\u5f55\u7684\u5176\u4ed6\u4ea4\u901a\u53c2\u4e0e\u8005。\u6570\u5b57\u5bf9\u5e94\u8ddf\u8e2a\u5bf9\u8c61，\u4e0d\u8868\u793a\u5df2\u7ecf\u8bc6\u522b\u4e86\u8f66\u8f86\u989c\u8272。\u7ea2\u7eff\u706f\u901a\u8fc7\u5730\u56fe\u8fde\u63a5\u9053\u8def\u7f16\u53f7\u5339\u914d，\u4e0d\u662f\u51ed\u753b\u9762\u989c\u8272\u731c\u6d4b。</p>'''
 for w in manifest:
  r,g,center,rot=extract(w);records.append(r);fig,ax=plt.subplots(figsize=(12,9))
  for n in g.nodes.values():
   xy=(np.asarray(n.baseline.coords)[:,:2]-center[:2])@rot;ax.plot(xy[:,0],xy[:,1],c='#d7dfe5',lw=.8)
  ax.scatter(0,0,c='black',s=90,label='Ego at anchor',zorder=5)
  for i,obj in enumerate(r['objects']):
   x,y=obj['xy_forward_left_m']
   if -30<x<70 and abs(y)<40:ax.scatter(x,y,c='#087f8c',s=45);ax.annotate(str(i+1),(x,y),xytext=(4,4),textcoords='offset points',fontsize=10)
  ax.set(xlim=(-30,70),ylim=(-40,40),xlabel='Forward (m)',ylabel='Left (m)',title=f'Scene {r["scene"]:02d}: exact-current tracked objects');ax.set_aspect('equal');ax.grid(alpha=.15);ax.legend();fig.tight_layout();fig.savefig(out/f'scene-{r["scene"]:02d}.png',dpi=140);plt.close(fig)
  page+=f'<article><h2>\u573a\u666f {r["scene"]:02d}</h2><p>\u5f53\u524d\u65f6\u523b：{len(r["objects"])} \u4e2a\u8ddf\u8e2a\u5bf9\u8c61；{len(r["signals"])} \u4e2a\u6709\u72b6\u6001\u8bb0\u5f55\u7684\u8def\u53e3\u8fde\u63a5\u9053\u8def。</p><table><tr><th>\u6307\u4ee4</th><th>\u9053\u8def\u9009\u62e9\u7ed3\u679c</th><th>\u8fd9\u6761\u9053\u8def\u5f53\u524d\u7684\u706f\u8272</th></tr>'
  for route in r['routes']:page+='<tr><td>'+route['instruction']+'</td><td>'+route.get('selection_reason',route.get('status',''))+'</td><td>'+html.escape(', '.join(x['id']+': '+x['signal']['classification'] for x in route.get('connectors',[])) or '\u6ca1\u6709\u53ef\u5339\u914d\u8bb0\u5f55')+'</td></tr>'
  page+=f'</table><img src="scene-{r["scene"]:02d}.png"><p>\u89c6\u9891\u5e27\u5bf9\u5e94\u72b6\u6001：{r["video"]["mapping_status"]}；GPS \u65f6\u95f4\u5dee：{r["video"]["gps_time_residual_s"]:.3f} \u79d2。</p>'
  try:
   import cv2
   cap=cv2.VideoCapture(r['video']['path']);cap.set(cv2.CAP_PROP_POS_FRAMES,r['video']['video_frame']);ok,frame=cap.read();cap.release()
   if ok:cv2.imwrite(str(out/f'video-{r["scene"]:02d}.jpg'),frame);page+=f'<p><b>\u524d\u89c6\u89c6\u9891\u53c2\u8003\u5e27：</b>\u5c1a\u4e0d\u80fd\u4f5c\u4e3a\u8f66\u8f86\u8eab\u4efd\u4e0e\u5730\u56fe\u4f4d\u7f6e\u5df2\u7ecf\u5bf9\u5e94\u6210\u529f\u7684\u8bc1\u636e。</p><img src="video-{r["scene"]:02d}.jpg">'
  except ImportError:r['video']['extraction']='opencv_not_available'
  page+='</article>';print(json.dumps({'scene':r['scene'],'objects':len(r['objects']),'signals':len(r['signals']),'video':r['video']['mapping_status']}),flush=True)
 (out/'contexts.json').write_text(json.dumps(records,indent=2));(out/'index.html').write_text(page,encoding='utf-8')
if __name__=='__main__':main()
