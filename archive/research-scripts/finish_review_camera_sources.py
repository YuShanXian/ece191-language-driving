import csv,json,subprocess,sys,sqlite3
from mtr_project.paths import ROOT
subprocess.run([sys.executable,str(ROOT/'scripts/prepare_human_camera_view.py')],check=True)
base=ROOT/'runs/project-v3/language-choice-v1/report-reviewed/human-review'
p=base/'real-camera/sources.json';records=json.loads(p.read_text())
clip='2021.07.16.21.17.55_veh-26_03772_03842'
with (ROOT/'data/doplan'/clip/'gps.csv').open() as f:rows=list(csv.DictReader(f))
times=[int(r['timestamp_us']) for r in rows]
e=json.loads((base.parent/'evaluation.json').read_text())['windows'][6]['source_window']
i=min(range(len(times)),key=lambda i:abs(times[i]-e['timestamp_us']))
v=json.loads((ROOT/'runs/project-v2/video-alignment'/clip/'video-audit.json').read_text())
front=next(x for x in v['videos'] if x['file'].endswith('/F0.mp4'))
records.append({'scene':7,'video':front['file'],'video_frame':i,'video_seconds':i/front['playback_fps'],
'timestamp_offset_seconds':(times[i]-e['timestamp_us'])/1e6,'playback_rate':.25,
'alignment_scope':'Approximate GPS row based location; 344 video frames vs 345 GPS rows, omitted-frame location unresolved.',
'alignment_note':'\u8fd1\u4f3c\u5b9a\u4f4d：\u89c6\u9891\u6bd4 GPS \u5c11 1 \u5e27，\u7f3a\u5e27\u4f4d\u7f6e\u5c1a\u672a\u786e\u8ba4。\u6b64\u5904\u6309 GPS \u5e8f\u53f7\u5b9a\u4f4d，\u4e0d\u80fd\u5f53\u4f5c\u7cbe\u786e\u540c\u6b65。'})
p.write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')
server=ROOT/'scripts/serve_human_review.py'
s=server.read_text(encoding='utf-8-sig').replace('r"/video/[1-4]"','r"/video/[1-7]"')
server.write_text(s,encoding='utf-8')
page=base/'round-2/index.html';s=page.read_text(encoding='utf-8-sig')
s=s.replace('\u5df2\u6309\u73b0\u6709\u65f6\u95f4\u6620\u5c04\u5b9a\u4f4d，\u5e76\u4ee5 0.25 \u500d\u901f\u64ad\u653e，\u63a5\u8fd1\u5b9e\u9645\u901f\u5ea6。',"""'+(src.alignment_note||'\u5df2\u6309\u73b0\u6709\u65f6\u95f4\u6620\u5c04\u5b9a\u4f4d，\u5e76\u4ee5 0.25 \u500d\u901f\u64ad\u653e，\u63a5\u8fd1\u5b9e\u9645\u901f\u5ea6。')+'""")
s=s.replace("v.ontimeupdate=()=>{if(v.currentTime>src.video_seconds+1.6&&!v.paused)v.pause();};","")
page.write_text(s,encoding='utf-8')
print('Sources available:',[r['scene'] for r in records])
