import json,html
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from execute_language_plan_v2 import execute
from mtr_project.paths import ROOT
out=ROOT/'runs/project-v3/doplan-multistep-v2';out.mkdir(exist_ok=True)
data=json.loads((ROOT/'runs/project-v3/recording-demo-v1/data.json').read_text())['scenes']
records=[];seen=set()
for folder in sorted((ROOT/'runs/project-v3/llm-parser-v2').glob('20261020-*')):
 if not (folder/'parsed.json').exists():continue
 req=json.loads((folder/'request.json').read_text(encoding='utf-8-sig'));plan=json.loads((folder/'parsed.json').read_text(encoding='utf-8-sig'))
 key=(req['scene'],req['instruction'])
 if key in seen:continue
 seen.add(key)
 r=execute(req['scene'],plan);(folder/'execution.json').write_text(json.dumps(r,indent=2))
 pts=np.asarray(r['points']);assert np.isfinite(pts).all();assert len(pts)==len(r['speed_mps'])
 assert np.allclose(pts[0],[0,0])
 for a,b in zip(r['stages'],r['stages'][1:]):
  assert a['status']=='completed_offline';assert a['end_point']==b['start_point'];assert np.allclose(a['end_xy'],b['start_xy'])
 fig,ax=plt.subplots(figsize=(12,9));scene=data[str(req['scene'])]
 for road in scene['roads']:
  q=np.asarray(road);ax.plot(q[:,0],q[:,1],color='#d5dee4',lw=1)
 colors=['#087f8c','#e27830','#8159b6','#c53a63']
 for st in r['stages']:
  p=pts[st['start_point']:st['end_point']+1]
  if len(p)>1:ax.plot(p[:,0],p[:,1],lw=3.5,color=colors[st['index']%4],label=f"Step {st['index']+1}: {st['action'].replace('_',' ')}")
 ax.scatter(0,0,c='black',s=50,label='Starting position',zorder=5)
 ax.set(xlim=(min(-20,pts[:,0].min()-10),max(45,pts[:,0].max()+10)),ylim=(min(-30,pts[:,1].min()-10),max(35,pts[:,1].max()+10)),xlabel='Forward from initial pose (m)',ylabel='Left from initial pose (m)',title=f"Scene {req['scene']:02d} | {r['status'].replace('_',' ')}")
 ax.set_aspect('equal',adjustable='box');ax.legend();ax.grid(alpha=.15);fig.tight_layout();name=f'case-{len(records)+1:02d}.png';fig.savefig(out/name,dpi=150);plt.close(fig)
 matches=[x for x in scene['doplan']['labels'] if x['passenger_instruction']==req['instruction']]
 record={'instruction':req['instruction'],'scene':req['scene'],'source':'doPlan original' if matches else 'synthetic test','annotation_ids':[x['annotation_id'] for x in matches],'conditional_window_overlap':any(x['overlaps_scene_under_gps_row_mapping'] for x in matches),'parser_status':plan['status'],'parsed_stages':plan['stages'],'execution':r,'run':folder.name,'figure':name}
 records.append(record);print(json.dumps({k:record[k] for k in ['instruction','scene','source']})+' '+r['status'],flush=True)
(out/'evaluation.json').write_text(json.dumps(records,indent=2))
head='''<!doctype html><meta charset="utf-8"><title>doPlan multi-step test</title><style>body{font:19px Segoe UI,sans-serif;background:#f4f7fb;color:#153249;max-width:1250px;margin:40px auto;padding:20px}article{background:white;border-radius:15px;padding:28px;margin:30px 0;break-before:page}img{width:100%}li{margin:14px 0}small{color:#62717d}h2{color:#087f8c}</style><h1>doPlan：\u4ece\u4e00\u53e5\u8bdd\u5230\u8fde\u7eed\u591a\u4e2a\u52a8\u4f5c</h1><p>\u8fd9\u8f6e\u6d4b\u8bd5\u7684\u662f：LLM \u80fd\u5426\u4fdd\u7559\u539f\u6307\u4ee4\u4e2d\u7684\u52a8\u4f5c\u548c\u6761\u4ef6，\u4ee5\u53ca\u5730\u56fe\u7a0b\u5e8f\u80fd\u5426\u4ece\u4e0a\u4e00\u6b65\u7ed3\u675f\u7684\u4f4d\u7f6e\u7ee7\u7eed\u751f\u6210\u4e0b\u4e00\u6b65\u8f68\u8ff9。\u56fe\u4e2d\u9ed1\u70b9\u662f\u8d77\u70b9，\u7070\u7ebf\u662f\u5730\u56fe\u8f66\u9053\u4e2d\u5fc3\u7ebf，\u4e0d\u540c\u989c\u8272\u8868\u793a\u4e0d\u540c\u6b65\u9aa4。</p><p><b>\u5b8c\u6210\u79bb\u7ebf\u8f68\u8ff9</b>\u53ea\u8868\u793a\u7a0b\u5e8f\u751f\u6210\u5e76\u68c0\u67e5\u4e86\u8fd9\u4e9b\u52a8\u4f5c\u7684\u51e0\u4f55\u8f68\u8ff9，\u4e0d\u8868\u793a\u771f\u5b9e\u9a7e\u9a76\u6d4b\u8bd5\u901a\u8fc7。\u539f\u6807\u7b7e\u5c5e\u4e8e\u540c\u4e00\u89c6\u9891，\u4f46\u4e0d\u4e00\u5b9a\u5c5e\u4e8e\u5f53\u524d\u622a\u56fe\u65f6\u523b；\u8fd9\u662f\u80fd\u529b\u6d4b\u8bd5，\u4e0d\u80fd\u5f53\u4f5c doPlan \u6570\u636e\u96c6\u6210\u7ee9。</p>'''
from collections import Counter
counts=Counter(r['execution']['status'] for r in records)
head+='<p><b>\u672c\u8f6e\u6837\u4f8b\u6570：</b>'+str(len(records))+'；\u5176\u4e2d\u539f\u59cb doPlan \u6307\u4ee4 '+str(sum(r['source']=='doPlan original' for r in records))+' \u6761，\u8865\u5145\u6d4b\u8bd5\u6307\u4ee4 '+str(sum(r['source']!='doPlan original' for r in records))+' \u6761。\u4e0d\u662f\u5168\u91cf\u6d4b\u8bd5。</p>'
names={'completed_offline':'\u5df2\u7ecf\u751f\u6210\u8fde\u7eed\u8f68\u8ff9，\u7b49\u5f85\u4eba\u5de5\u770b\u56fe\u590d\u6838','waiting_for_observation':'\u542c\u61c2\u4e86，\u4f46\u9700\u8981\u8bc6\u522b\u89e6\u53d1\u6761\u4ef6\u540e\u624d\u80fd\u6267\u884c','blocked':'\u542c\u61c2\u4e86，\u4f46\u6267\u884c\u6240\u9700\u80fd\u529b\u5c1a\u672a\u5b9e\u73b0\u6216\u5730\u56fe\u4e2d\u6ca1\u6709\u76ee\u6807','partial':'\u524d\u9762\u7684\u52a8\u4f5c\u751f\u6210\u4e86\u8f68\u8ff9，\u540e\u7eed\u52a8\u4f5c\u5c1a\u672a\u5b8c\u6210','incomplete':'\u751f\u6210\u4e86\u8f68\u8ff9，\u4f46\u6ca1\u6709\u5b8c\u6210\u8981\u6c42\u7684\u52a8\u4f5c','review_required':'\u751f\u6210\u4e86\u8f68\u8ff9，\u4f46\u9053\u8def\u6216\u8f6c\u5411\u68c0\u67e5\u6ca1\u6709\u901a\u8fc7','needs_clarification':'\u6307\u4ee4\u4fe1\u606f\u4e0d\u8db3，\u672a\u6267\u884c','invalid_plan':'\u672a\u83b7\u5f97\u53ef\u6267\u884c\u7684\u52a8\u4f5c\u5217\u8868'}
for i,r in enumerate(records,1):
 e=r['execution'];head+=f'<article><h2>\u6d4b\u8bd5 {i:02d} · \u573a\u666f {r["scene"]:02d}</h2><p><b>\u8f93\u5165\u6307\u4ee4：</b>{html.escape(r["instruction"])}</p><p><b>\u6d4b\u8bd5\u7ed3\u8bba：</b>{names.get(e["status"],e["status"])}</p><p><small>\u6765\u6e90：{r["source"]}；\u5f53\u524d\u7a97\u53e3\u6761\u4ef6\u5339\u914d：{r["conditional_window_overlap"]}</small></p><ol>'
 for j,st in enumerate(r['parsed_stages']):
  result=next((x for x in e['stages'] if x['index']==j),None)
  head+=f'<li>{html.escape(st["source_clause"])}<br>\u52a8\u4f5c：{st["action"]}；\u89e6\u53d1\u6761\u4ef6：{html.escape(st["trigger_text"] or st["trigger"])}<br>\u7ed3\u679c：{html.escape(names.get(result["status"],result["status"]) if result else "\u672a\u5f00\u59cb；\u524d\u4e00\u6b65\u6ca1\u6709\u5b8c\u6210")}<br><small>{html.escape(result.get("reason", "") if result else "")}</small></li>'
 head+=f'</ol><img src="{r["figure"]}" alt="Map and sequential planned trajectories"></article>'
(out/'index.html').write_text(head,encoding='utf-8')
print('All finite-output and stage-continuity assertions passed; report:',out/'index.html')
