import json,os,cv2
from pathlib import Path
from mtr_project.paths import ROOT
base=ROOT/'runs/project-v3/language-choice-v1/report-reviewed';a=json.loads((base/'evaluation.json').read_text());out=base/'human-review/real-camera';out.mkdir(parents=True,exist_ok=True)
parts=['<!doctype html><meta charset="utf-8"><title>\u771f\u5b9e\u76f8\u673a\u753b\u9762</title><style>body{font:20px/1.7 sans-serif;max-width:1200px;margin:30px auto}video,img{width:100%}section{margin:50px 0}a{color:#176b9a}</style><h1>\u4eba\u5de5\u8bc4\u5ba1：\u771f\u5b9e\u524d\u89c6\u76f8\u673a</h1><p>\u573a\u666f01–04\u6709\u672c\u5730\u89c6\u9891；05–07\u5c1a\u7f3a。\u89c6\u9891\u65f6\u95f4\u6309\u5df2\u6709\u6620\u5c04\u5b9a\u4f4d，\u8be5\u6620\u5c04\u4ecd\u662f\u6761\u4ef6\u6027\u5bf9\u9f50，\u4e0d\u80fd\u5f53\u4f5c\u9010\u5e27\u72ec\u7acb\u8ba4\u8bc1。</p>'];records=[]
for r in a['windows']:
 w=r['source_window'];clip=w['clip'];mapping=ROOT/'runs/project-v2/video-alignment'/clip/'viewer-alignment.json'
 if not mapping.exists():continue
 m=json.loads(mapping.read_text());entry=min(m['frame_mapping'],key=lambda x:abs(x['timestamp_us']-w['timestamp_us']));v=next(v for v in m['videos'] if v['file'].endswith('/F0.mp4'));path=ROOT/v['file'];frame=entry['video_frame_zero_based'];fps=v['playback_fps'];t=frame/fps
 cap=cv2.VideoCapture(str(path));cap.set(cv2.CAP_PROP_POS_FRAMES,frame);ok,img=cap.read();cap.release()
 if not ok:raise RuntimeError('Frame unavailable')
 filename=f'scene-{r["number"]:02d}-front.jpg';cv2.imwrite(str(out/filename),img)
 # Most release clips play 4x real-time; derive factor from mapping instead of assuming it.
 duration=(m['frame_mapping'][-1]['timestamp_us']-m['frame_mapping'][0]['timestamp_us'])/1e6;play=(m['frame_mapping'][-1]['video_frame_zero_based']-m['frame_mapping'][0]['video_frame_zero_based'])/fps;rate=play/duration
 offset=(entry['timestamp_us']-w['timestamp_us'])/1e6;relative=os.path.relpath(path,out).replace('\\','/')
 parts.append(f'<section><h2>\u573a\u666f {r["number"]:02d}</h2><p>\u5f53\u524d\u65f6\u523b\u7684\u524d\u89c6\u753b\u9762；\u65f6\u95f4\u5339\u914d\u504f\u5dee {offset:+.3f} \u79d2。\u89c6\u9891\u7ea6\u4ee5 {rate:.2f} \u500d\u64ad\u653e\u901f\u5ea6\u8fd8\u539f\u771f\u5b9e\u65f6\u95f4。</p><img src="{filename}"><video controls preload="metadata" data-current="{t}" data-rate="{rate}"><source src="{relative}" type="video/mp4"></video><button onclick="let v=this.previousElementSibling;v.currentTime=Number(v.dataset.current);v.pause()">\u56de\u5230\u5f53\u524d\u65f6\u523b</button><p>\u89c6\u9891\u6765\u81ea\u771f\u5b9e\u9a7e\u9a76\u8bb0\u5f55，\u5c55\u793a\u5b9e\u9645\u9a7e\u9a76\u5458\u7684\u884c\u4e3a，\u5e76\u975eMTR\u6216\u8bed\u8a00\u6307\u4ee4\u63a7\u5236\u7684\u7ed3\u679c。</p></section>')
 records.append({'scene':r['number'],'video':v['file'],'video_frame':frame,'video_seconds':t,'timestamp_offset_seconds':offset,'playback_rate':rate,'alignment_scope':'conditional mapping from existing audit; not independently accessenticated at this anchor'})
parts.append('<script>document.querySelectorAll("video").forEach(v=>v.addEventListener("loadedmetadata",()=>{v.currentTime=Number(v.dataset.current);v.playbackRate=Number(v.dataset.rate)}))</script>');(out/'index.html').write_text('\n'.join(parts),encoding='utf-8');(out/'sources.json').write_text(json.dumps(records,indent=2));print(json.dumps(records))
