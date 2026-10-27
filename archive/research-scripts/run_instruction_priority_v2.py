import json,pickle,html
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from mtr_project.paths import ROOT,sha256,write_json
from evaluate_candidate_checks import load_graph
from instruction_priority_v2 import select_priority
base=ROOT/'runs/project-v3/language-choice-v1/report-reviewed'
old=json.loads((base/'evaluation.json').read_text())
out=ROOT/'runs/project-v3/instruction-priority-v2';out.mkdir(exist_ok=True)
font_manager.fontManager.addfont('/mnt/c/Windows/Fonts/msyh.ttc')
plt.rcParams['font.family']=font_manager.FontProperties(fname='/mnt/c/Windows/Fonts/msyh.ttc').get_name()
plt.rcParams['axes.unicode_minus']=False
labels=['\u76f4\u884c\u6307\u4ee4','\u5de6\u8f6c\u6307\u4ee4','\u53f3\u8f6c\u6307\u4ee4','\u5411\u5de6\u6362\u9053\u6307\u4ee4','\u5411\u53f3\u6362\u9053\u6307\u4ee4']
risknames={'road_footprint':'\u8f66\u8eab\u8d8a\u51fa\u5730\u56fe\u9053\u8def\u8303\u56f4','motion':'\u52a0\u901f\u5ea6\u7b49\u8fd0\u52a8\u6307\u6807\u8d85\u9650','constant_velocity_collision':'\u7b80\u5316\u9884\u6d4b\u63d0\u793a\u78b0\u649e\u98ce\u9669','observed_start_road_route':'\u672a\u5339\u914d\u5230\u5b8c\u6574\u9053\u8def\u8def\u5f84','refinement_deviation':'\u5e73\u6ed1\u6539\u52a8\u8d85\u8fc7\u539f\u8bbe\u5b9a\u8303\u56f4'}
evnames={'road_and_geometry':'\u8def\u7ebf\u65b9\u5411\u4e0e\u5730\u56fe\u5339\u914d\u5747\u652f\u6301','geometry_only':'\u4ec5\u8f68\u8ff9\u5f62\u72b6\u7b26\u5408，\u5b8c\u6574\u9053\u8def\u8def\u5f84\u672a\u786e\u8ba4','map_lane_transition':'\u5730\u56fe\u5339\u914d\u8bc6\u522b\u5230\u6362\u9053','map_lane_target':'\u8fdb\u5165\u6307\u5b9a\u4fa7\u76f8\u90bb\u8f66\u9053\u5206\u652f，\u5e76\u5728\u7ed3\u675f\u65f6\u4fdd\u6301\u5176\u4e2d','lateral_motion_only':'\u4ec5\u53d1\u73b0\u6a2a\u5411\u79fb\u52a8，\u5c1a\u4e0d\u80fd\u786e\u8ba4\u6362\u9053'}
style='<style>body{font:19px/1.7 sans-serif;background:#eef2f5;color:#183345;max-width:1200px;margin:30px auto;padding:20px}section{background:white;padding:25px;margin:25px 0;border-radius:12px}img{width:100%}a{color:#176b9a}.small{font-size:15px;color:#526a7b}.risk{background:#fff0d8;padding:12px}h1{font-size:30px}h2{font-size:26px}</style>'
records=[]
for r in old['windows']:
 w=r['source_window'];run=ROOT/'runs'/w['run'];folder=ROOT/'samples'/w['sample']
 check=json.loads((run/'ambiguity_aware_feasibility.json').read_text());rows=check['candidates']
 c=json.loads((folder/'conversion.json').read_text());ego=pickle.load(open(folder/c['scenario'],'rb'))['tracks']['ego']['state']
 g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map'])
 center=np.load(run/'internal_0000.npz')['center'];xy=np.load(run/'refined_v2_candidates.npz')['world_xy']
 rot=np.array([[np.cos(center[6]),-np.sin(center[6])],[np.sin(center[6]),np.cos(center[6])]])
 local=lambda p:(np.asarray(p)[...,:2]-center[:2])@rot
 number=r['number'];choices=[]
 page=['<!doctype html><meta charset="utf-8">'+style,f'<a href="index.html">\u8fd4\u56de\u603b\u89c8</a><h1>\u573a\u666f {number:02d} · \u6307\u4ee4\u4f18\u5148\u5b9e\u9a8c</h1><p>\u84dd\u7ebf：\u672c\u8f6e\u9009\u62e9；\u6a59\u8272\u865a\u7ebf：\u65e7\u7a0b\u5e8f\u9009\u62e9。\u98ce\u9669\u5355\u72ec\u5217\u51fa，\u4e0d\u518d\u76f4\u63a5\u5426\u51b3。</p><p><a target="_blank" href="http://localhost:8768/#scene-{number}">\u6253\u5f00\u8fd9\u4e2a\u573a\u666f\u7684\u89c6\u9891\u4e0e\u539f\u4eba\u5de5\u8bc4\u4ef7</a></p>']
 for j,prev in enumerate(r['choices']):
  result=select_priority(rows,xy,center,prev['action'],graph=g,start_nodes=check['summary']['past_only_start_nodes']);selected=result['candidate'];oldid=prev['choice']['candidate']
  choices.append({'instruction':prev['instruction'],'action':prev['action'],'old_candidate':oldid,**result})
  fig,ax=plt.subplots(figsize=(11,8.5));past=local(ego['position'][:21,:2]);extent=[past,np.array([[0,0],[40,0]])]
  for node in g.nodes.values():
   p=local(node.baseline.coords);ax.plot(p[:,0],p[:,1],c='#cbd3dc',lw=1)
  ax.plot(past[:,0],past[:,1],c='#222',lw=2,label='\u8f66\u8f86\u8fc7\u53bb2\u79d2\u7684\u5b9e\u9645\u8def\u7ebf');ax.scatter(0,0,c='#222',s=60,label='\u5f53\u524d\u4f4d\u7f6e',zorder=10)
  if oldid is not None:
   p=local(np.vstack([center[:2],xy[oldid-1]]));extent.append(p);ax.plot(p[:,0],p[:,1],'--',c='#db8d2b',lw=3,label=f'\u65e7\u9009\u62e9 #{oldid}')
  if selected is not None:
   p=local(np.vstack([center[:2],xy[selected-1]]));extent.append(p);ax.plot(p[:,0],p[:,1],c='#246ab1',lw=3.5,label=f'\u6307\u4ee4\u4f18\u5148\u9009\u62e9 #{selected}')
  points=np.vstack(extent);lo=points.min(0)-12;hi=points.max(0)+12;span=np.maximum(hi-lo,50);mid=(lo+hi)/2
  ax.set_xlim(mid[0]-span[0]/2,mid[0]+span[0]/2);ax.set_ylim(mid[1]-span[1]/2,mid[1]+span[1]/2);ax.set_aspect('equal');ax.grid(alpha=.2)
  ax.set_xlabel('\u6cbf\u5f53\u524d\u8f66\u5934\u65b9\u5411\u5411\u524d（\u7c73）');ax.set_ylabel('\u5411\u5de6（\u7c73）');ax.legend(fontsize=11)
  title=f'\u9009\u4e2d\u8def\u7ebf #{selected}' if selected is not None else '\u73b0\u6709\u5019\u9009\u4e2d\u6ca1\u6709\u6ee1\u8db3\u672c\u8f6e\u52a8\u4f5c\u5b9a\u4e49\u7684\u8def\u7ebf'
  ax.set_title(f'\u573a\u666f {number:02d} · {labels[j]}\n{title}',fontsize=18);fig.tight_layout()
  image=f'scene-{number:02d}-command-{j}.png';fig.savefig(out/image,dpi=150);plt.close(fig)
  page.append(f'<section><h2>{labels[j]}</h2><p><b>\u7ed3\u679c：{title}。</b></p>')
  if selected is not None:
   page.append(f'<p>\u4f9d\u636e：{evnames[result["evidence"]]}。\u8fd9\u4ecd\u9700\u4eba\u5de5\u786e\u8ba4，\u4e0d\u8ba1\u4f5c\u5df2\u9a8c\u8bc1\u6210\u529f。</p>')
   flags=result['risk_flags'];page.append('<p class="risk">\u68c0\u67e5\u53d1\u73b0：'+('；'.join(risknames.get(k,k) for k in flags) if flags else '\u672a\u89e6\u53d1\u73b0\u6709\u68c0\u67e5\u4e2d\u7684\u98ce\u9669\u9879')+'。</p>')
   f=result['features'];page.append(f'<p class="small">6\u79d2\u5185\u822a\u5411\u6539\u53d8 {f["heading_change_deg"]:.1f}°；\u7ec8\u70b9\u5411\u5de6\u504f\u79fb {f["left_m"]:.1f} \u7c73。\u7ea2\u7eff\u706f\u53ca\u8f66\u9053\u7ebf\u9650\u5236\u5c1a\u672a\u81ea\u52a8\u68c0\u67e5。</p>')
  page.append(f'<img src="{image}"></section>')
 page.append('<p class="small">\u53ea\u91cd\u9009\u5df2\u4fdd\u5b58\u7684 MTR \u6d3e\u751f\u5019\u9009；\u6ca1\u6709\u8bad\u7ec3\u6a21\u578b、\u6dfb\u52a0\u624b\u753b\u8def\u7ebf\u6216\u8bfb\u53d6\u771f\u5b9e\u672a\u6765\u6765\u9009\u62e9。</p>')
 (out/f'scene-{number:02d}.html').write_text('\n'.join(page),encoding='utf-8')
 records.append({'scene':number,'choices':choices,'candidate_file':str((run/'refined_v2_candidates.npz').relative_to(ROOT)),'candidate_sha256':sha256(run/'refined_v2_candidates.npz')})
 print('Completed scene',number,flush=True)
summary={}
for j,label in enumerate(labels):
 ch=[r['choices'][j] for r in records]
 summary[label]={'old_outputs':sum(c['old_candidate'] is not None for c in ch),'new_outputs':sum(c['candidate'] is not None for c in ch),
 'map_supported':sum(c.get('evidence') in ('road_and_geometry','map_lane_target') for c in ch),
 'provisional_only':sum(c.get('evidence') in ('geometry_only','lateral_motion_only') for c in ch),
 'with_risk_flags':sum(bool(c.get('risk_flags')) for c in ch)}
write_json(out/'results.json',{'policy':'offline_instruction_priority_v2','summary':summary,'windows':records,'selection_code_sha256':sha256(ROOT/'scripts/instruction_priority_v2.py'),'scope':'Outputs and geometry evidence, NOT success rate. Seven development scenes; human reviews not used by selection.'})
page=['<!doctype html><meta charset="utf-8">'+style,'<h1>\u6307\u4ee4\u4f18\u5148 · 7\u4e2a\u573a\u666f\u91cd\u9009\u7ed3\u679c</h1><p>\u5148\u627e\u7b26\u5408\u6307\u4ee4\u7684\u8def\u7ebf，\u518d\u663e\u793a\u98ce\u9669。\u4fdd\u7559\u65e7\u7ed3\u679c\u5bf9\u7167；\u6ca1\u6709\u5019\u9009\u65f6\u660e\u786e\u5199\u6ca1\u6709。</p><p><b>\u8fd9\u91cc\u7edf\u8ba1“\u9009\u51fa\u8def\u7ebf”，\u4e0d\u662f“\u6210\u529f\u9a7e\u9a76”。\u6a2a\u5411\u79fb\u52a8\u4e0d\u81ea\u52a8\u7b97\u6362\u9053。</b></p><table><tr><th>\u6307\u4ee4</th><th>\u65e7\u8f93\u51fa</th><th>\u65b0\u8f93\u51fa</th><th>\u5730\u56fe\u652f\u6301</th><th>\u4ec5\u51e0\u4f55\u7ebf\u7d22</th></tr>']
for label,s in summary.items():page.append(f'<tr><td>{label}</td><td>{s["old_outputs"]}/7</td><td>{s["new_outputs"]}/7</td><td>{s["map_supported"]}/7</td><td>{s["provisional_only"]}/7</td></tr>')
page.append('</table><p>\u672c\u8f6e“\u76f4\u884c”\u6307\u57fa\u672c\u6cbf\u5f53\u524d\u8f66\u5934\u65b9\u5411\u524d\u8fdb；“\u6cbf\u5f53\u524d\u9053\u8def\u884c\u9a76”\u662f\u53e6\u4e00\u4e2a\u610f\u56fe。\u6b64\u7248\u672c\u4ecd\u4f7f\u7528\u56fa\u5b9a\u82f1\u6587\u6307\u4ee4\u89c4\u5219。</p>')
for r in records:page.append(f'<section><a href="scene-{r["scene"]:02d}.html">\u573a\u666f {r["scene"]:02d}：\u67e5\u770b\u4e94\u6761\u6307\u4ee4\u7684\u5927\u56fe、\u65e7\u65b0\u5bf9\u7167\u4e0e\u98ce\u9669</a></section>')
page.append('<p class="small">\u4f7f\u7528\u539f\u6709\u6709\u9650\u5e73\u6ed1\u540e\u768464\u6761MTR\u5019\u9009，\u672a\u4fee\u6539\u751f\u6210\u6a21\u578b。\u6240\u67097\u4e2a\u573a\u666f\u7528\u4e8e\u5f00\u53d1，\u4e0d\u662f\u72ec\u7acb\u6d4b\u8bd5\u96c6。\u6a21\u578b\u5206\u6570\u4e0d\u662f\u5b89\u5168\u6982\u7387。</p>')
(out/'index.html').write_text('\n'.join(page),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))

