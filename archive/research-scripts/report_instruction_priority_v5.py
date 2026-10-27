"""Large visual report, source attribution and original human notes kept separate."""
import json,pickle,html
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph
out=ROOT/'runs/project-v3/instruction-priority-v5'
data=json.loads((out/'results.json').read_text())
assert len(data['windows'])==7,'Wait for experiment to finish'
reviews=json.loads((ROOT/'runs/project-v3/language-choice-v1/report-reviewed/human-review/round-2/reviews.json').read_text())['reviews']
sources={r['scene']:r for r in json.loads((ROOT/'runs/project-v3/language-choice-v1/report-reviewed/human-review/real-camera/sources.json').read_text())}
font_manager.fontManager.addfont('/mnt/c/Windows/Fonts/msyh.ttc');plt.rcParams['font.family']=font_manager.FontProperties(fname='/mnt/c/Windows/Fonts/msyh.ttc').get_name();plt.rcParams['axes.unicode_minus']=False
labels=['\u76f4\u884c\u6307\u4ee4','\u5de6\u8f6c\u6307\u4ee4','\u53f3\u8f6c\u6307\u4ee4','\u5411\u5de6\u6362\u9053\u6307\u4ee4','\u5411\u53f3\u6362\u9053\u6307\u4ee4']
risknames={'road_footprint':'\u8f66\u8eab\u8d8a\u51fa\u5730\u56fe\u9053\u8def\u8303\u56f4','motion':'\u52a0\u901f\u5ea6\u7b49\u8fd0\u52a8\u6307\u6807\u8d85\u9650','constant_velocity_collision':'\u6052\u901f\u969c\u788d\u7269\u9884\u6d4b\u63d0\u793a\u78b0\u649e\u98ce\u9669','observed_start_road_route':'\u5168\u8fc7\u7a0b\u9053\u8def\u8fde\u63a5\u672a\u5339\u914d','refinement_deviation':'\u5e73\u6ed1\u6539\u52a8\u8d85\u51fa\u539f\u8bbe\u5b9a','ambiguous_start_lane':'\u5f53\u524d\u6240\u5c5e\u8f66\u9053\u6709\u591a\u4e2a\u53ef\u80fd','no_grounded_road_target':'\u672a\u786e\u8ba4\u5bf9\u5e94\u9053\u8def\u76ee\u6807','synthetic_direction_probe_not_MTR':'\u7a0b\u5e8f\u751f\u6210\u7684\u65b9\u5411\u6d4b\u8bd5\u7ebf，\u4e0d\u662f MTR \u5019\u9009'}
style='<style>body{font:19px/1.7 "Segoe UI",sans-serif;background:#edf2f6;color:#183345;max-width:1250px;margin:auto;padding:25px}section{background:white;padding:25px;margin:25px 0;border-radius:12px}img,video{width:100%}video{max-height:650px;background:#111}a{color:#176b9a}.small{font-size:15px;color:#526a7b}.risk{background:#fff0d8;padding:12px}h1{font-size:30px}h2{font-size:25px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border-bottom:1px solid #ccd8df;text-align:left}.pill{background:#e3f0eb;padding:12px}</style>'
probe_base=ROOT/'runs/project-v3/forced-direction-probes-v1'
probes={(p['scene'],p['command']):p for p in json.loads((probe_base/'results.json').read_text())['results']}
counts={'mtr':0,'supplement':0,'none':0,'with_risk_flags':0};matrix=np.zeros((7,5),int);missing=[]
for w in data['windows']:
 s=w['scene'];source=w['source_window'];run=ROOT/'runs'/source['run'];sample=ROOT/'samples'/source['sample']
 c=json.loads((sample/'conversion.json').read_text());ego=pickle.load(open(sample/c['scenario'],'rb'))['tracks']['ego']['state']
 graph=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);center=np.load(run/'internal_0000.npz')['center'];xy=np.load(run/'refined_v2_candidates.npz')['world_xy'];saved=np.load(out/f'scene-{s:02d}-selected.npz')
 rot=np.array([[np.cos(center[6]),-np.sin(center[6])],[np.sin(center[6]),np.cos(center[6])]])
 local=lambda p:(np.asarray(p)[...,:2]-center[:2])@rot
 src=sources[s]
 parts=['<!doctype html><meta charset="utf-8">'+style,f'<a href="index.html">\u8fd4\u56de\u603b\u89c8</a> · <a href="scene-{min(s+1,7):02d}.html">\u4e0b\u4e00\u4e2a\u573a\u666f →</a><h1>\u573a\u666f {s:02d} · \u6307\u4ee4\u4f18\u5148\u7ed3\u679c</h1>',
 f'<section><h2>\u5b9e\u9645\u9053\u8def\u89c6\u9891</h2><video controls preload="metadata" data-time="{src["video_seconds"]}" src="http://localhost:8768/video/{s}"></video><button onclick="let v=this.previousElementSibling;v.pause();v.currentTime=Number(v.dataset.time)">\u56de\u5230\u7ebf\u56fe\u5f53\u524d\u65f6\u523b</button><p class="small">\u771f\u5b9e\u9a7e\u9a76\u8bb0\u5f55，\u4e0d\u662f\u672c\u7a0b\u5e8f\u6267\u884c。'+html.escape(src.get('alignment_note','\u6309\u73b0\u6709\u65f6\u95f4\u6620\u5c04\u5b9a\u4f4d；\u7cbe\u786e\u9010\u5e27\u5bf9\u5e94\u672a\u72ec\u7acb\u9a8c\u8bc1。'))+'</p></section>',
 '<p>\u84dd\u7ebf＝\u672c\u8f6e\u9009\u62e9；\u6a59\u8272\u865a\u7ebf＝\u65e7\u9009\u62e9；\u7eff\u8272\u7c97\u7ebf＝\u8bc6\u522b\u5230\u7684\u9053\u8def\u76ee\u6807\u4e2d\u5fc3\u7ebf。\u7070\u7ebf\u662f\u5730\u56fe\u4e2d\u5fc3\u7ebf，\u4e0d\u662f\u8f66\u9053\u5b9e\u7ebf\u6216\u865a\u7ebf。</p>']
 for j,ch in enumerate(w['choices']):
  present=f'command_{j}' in saved
  if present:
   kind='mtr' if ch['source']=='MTR_refined' else 'supplement';counts[kind]+=1;matrix[s-1,j]=1 if kind=='mtr' else 2
   title='\u5df2\u627e\u5230\u901a\u5411\u76ee\u6807\u9053\u8def\u7684\u8def\u7ebf' if j<3 else '\u5df2\u627e\u5230\u8fdb\u5165\u76f8\u90bb\u8f66\u9053\u5206\u652f\u7684\u8def\u7ebf'
   source_name=f'MTR \u539f\u5019\u9009\u7684\u5e73\u6ed1\u7248\u672c #{ch["candidate"]}' if kind=='mtr' else '\u5730\u56fe\u751f\u6210\u7684\u8865\u5145\u8def\u7ebf（\u4e0d\u662f MTR \u8f93\u51fa）'
   if ch.get('risk_flags'):counts['with_risk_flags']+=1
  else:
   counts['none']+=1;missing.append({'scene':s,'command':labels[j]});title='\u5c1a\u672a\u627e\u5230\u5bf9\u5e94\u9053\u8def\u76ee\u6807\u548c\u8def\u7ebf';source_name='\u65e0'
  parts.append(f'<section><h2>{labels[j]} · {ch["instruction"]}</h2><p class="pill"><b>\u672c\u8f6e\u7ed3\u8bba：{title}。</b></p><p>\u8def\u7ebf\u6765\u6e90：{source_name}</p>')
  if present:
   flags=ch.get('risk_flags',[])
   parts.append('<p class="risk">\u98ce\u9669\u68c0\u67e5：'+('；'.join(risknames.get(k,k) for k in flags) if flags else '\u672a\u89e6\u53d1\u73b0\u6709\u68c0\u67e5\u9879\u76ee')+'。</p>')
   parts.append('<p class="small">\u52a8\u4f5c\u76ee\u6807\u901a\u8fc7\u7a0b\u5e8f\u68c0\u67e5，\u5c1a\u672a\u4eba\u5de5\u786e\u8ba4。\u7ea2\u7eff\u706f、\u8f66\u9053\u7ebf\u5408\u6cd5\u6027\u5c1a\u672a\u81ea\u52a8\u68c0\u67e5；\u672a\u62a5\u8b66\u4e0d\u7b49\u4e8e\u5b89\u5168。</p>')
  else:parts.append('<p>\u4e0d\u5f3a\u884c\u753b\u51fa\u4e00\u6761\u5192\u5145\u6210\u529f\u7684\u8def\u7ebf。\u53ef\u80fd\u662f\u6ca1\u6709\u5bf9\u5e94\u8f66\u9053、\u5019\u9009\u4e0d\u8db3，\u6216\u6307\u4ee4\u542b\u4e49\u9700\u8981\u660e\u786e；\u4e0d\u662f\u81ea\u52a8\u5224\u5b9a\u8be5\u52a8\u4f5c\u7edd\u5bf9\u4e0d\u53ef\u80fd。</p>')
  if present and ch.get('tracking'):
   cases=ch['tracking']['cases'];retained=sum(bool(ca.get('target_retained')) for ca in cases)
   worst=max(ca['metrics']['maximum_center_error_m'] for ca in cases)
   parts.append(f'<p><b>\u8f66\u8f86\u6a21\u578b\u8ddf\u8e2a：{retained}/3 \u79cd\u521d\u59cb\u8f6c\u5411\u8bbe\u7f6e\u4ecd\u6ee1\u8db3\u52a8\u4f5c\u76ee\u6807。</b> \u6700\u5927\u4f4d\u7f6e\u504f\u5dee {worst:.2f} \u7c73。</p>')
  if not present:
   probe=probes[(s,j)];retained=sum(ca['geometric_action_retained'] for ca in probe['cases'])
   parts.append(f'<p class="risk"><b>\u53e6\u63d0\u4f9b\u5f3a\u5236\u65b9\u5411\u63a2\u9488：</b>\u53ea\u9a8c\u8bc1\u671d\u6307\u5b9a\u65b9\u5411\u8fd0\u52a8，\u6ca1\u6709\u786e\u8ba4\u5bf9\u5e94\u9053\u8def\u6216\u8f66\u9053。\u5b83\u7531\u7a0b\u5e8f\u751f\u6210，\u4e0d\u662f MTR \u8f93\u51fa。{retained}/3 \u79cd\u521d\u59cb\u8f6c\u5411\u8bbe\u7f6e\u4fdd\u6301\u4e86\u51e0\u4f55\u52a8\u4f5c。</p>')
   parts.append('<p class="small">\u63a2\u9488\u98ce\u9669：'+html.escape('；'.join(risknames.get(k,k) for k in probe['risk_flags']))+'</p>')
  note=reviews[(s-1)*5+j]['reason']
  if note:parts.append('<p class="small">\u4f60\u5bf9\u65e7\u7ed3\u679c\u7684\u5907\u6ce8（\u672a\u7528\u4e8e\u9009\u62e9，\u4e5f\u672a\u81ea\u52a8\u5f53\u4f5c\u771f\u503c）：'+html.escape(note)+'</p>')
  fig,ax=plt.subplots(figsize=(11,8.5));past=local(ego['position'][:21,:2]);extent=[past,np.array([[0,0],[40,0]])]
  for node in graph.nodes.values():
   p=local(node.baseline.coords);ax.plot(p[:,0],p[:,1],c='#d1d7de',lw=1)
  if present:
   target=ch['features']['target'];keys=target.get('visited_target_nodes',[target.get('node')])
   for k,key in enumerate(keys):
    if key in graph.nodes:
     p=local(graph.nodes[key].baseline.coords);ax.plot(p[:,0],p[:,1],c='#58a187',lw=2.5,label='\u76ee\u6807\u9053\u8def\u4e2d\u5fc3\u7ebf' if k==0 else None)
  ax.plot(past[:,0],past[:,1],c='#222',lw=2.5,label='\u8fc7\u53bb2\u79d2\u5b9e\u9645\u8def\u7ebf');ax.scatter(0,0,s=65,c='#222',zorder=10,label='\u5f53\u524d\u4f4d\u7f6e')
  oldid=ch['old_candidate']
  if oldid:
   p=local(np.vstack([center[:2],xy[oldid-1]]));extent.append(p);ax.plot(p[:,0],p[:,1],'--',c='#db8d2b',lw=2.5,label=f'\u65e7\u9009\u62e9 #{oldid}')
  if present:
   p=local(saved[f'command_{j}']);extent.append(p);ax.plot(p[:,0],p[:,1],c='#246ab1',lw=3.5,label='\u672c\u8f6e\u9009\u62e9（'+('MTR\u5019\u9009' if kind=='mtr' else '\u5730\u56fe\u8865\u5145')+'）')
  if not present:
   p=local(np.load(probe_base/f'scene-{s:02d}-command-{j}.npz')['points']);extent.append(p)
   ax.plot(p[:,0],p[:,1],c='#a64e9c',lw=3.5,label='\u5f3a\u5236\u65b9\u5411\u63a2\u9488（\u65e0\u9053\u8def\u76ee\u6807）')
  if present:
   simpath=out/f'scene-{s:02d}-command-{j}-steer+0.npz'
   if not simpath.exists():simpath=ROOT/f'runs/project-v3/instruction-priority-v4/scene-{s:02d}-command-{j}-steer+0.npz'
   if not simpath.exists():simpath=ROOT/f'runs/project-v3/instruction-priority-v3/tracking/scene-{s:02d}-command-{j}-steer+0.npz'
  else:simpath=probe_base/f'scene-{s:02d}-command-{j}-steer+0.npz'
  if simpath.exists():
   sim=local(np.load(simpath)['center_xy']);extent.append(sim);ax.plot(sim[:,0],sim[:,1],':',c='#c64b30',lw=2,label='\u7b80\u5316\u8f66\u8f86\u6a21\u578b\u5b9e\u9645\u8d70\u51fa\u7684\u7ebf')
  points=np.vstack(extent);lo=points.min(0)-12;hi=points.max(0)+12;span=np.maximum(hi-lo,50);mid=(lo+hi)/2
  ax.set_xlim(mid[0]-span[0]/2,mid[0]+span[0]/2);ax.set_ylim(mid[1]-span[1]/2,mid[1]+span[1]/2);ax.set_aspect('equal');ax.grid(alpha=.15)
  ax.set_xlabel('\u6cbf\u5f53\u524d\u8f66\u5934\u65b9\u5411\u5411\u524d（\u7c73）');ax.set_ylabel('\u5411\u5de6（\u7c73）');ax.legend(fontsize=11)
  ax.set_title(f'\u573a\u666f {s:02d} · {labels[j]}\n'+(title if present else '\u6709\u65b9\u5411\u6d4b\u8bd5\u7ebf，\u672a\u786e\u8ba4\u5bf9\u5e94\u9053\u8def\u76ee\u6807'),fontsize=18)
  fig.tight_layout();name=f'scene-{s:02d}-command-{j}.png';fig.savefig(out/name,dpi=150);plt.close(fig)
  parts.append(f'<img src="{name}"></section>')
 parts.append('<script>document.querySelectorAll("video").forEach(v=>v.onloadedmetadata=()=>{v.currentTime=Number(v.dataset.time);v.playbackRate=.25})</script>')
 (out/f'scene-{s:02d}.html').write_text('\n'.join(parts),encoding='utf-8')
fig,ax=plt.subplots(figsize=(11,7));from matplotlib.colors import ListedColormap
ax.imshow(matrix,cmap=ListedColormap(['#e7ebef','#459b87','#6195c9']),vmin=0,vmax=2)
ax.set_xticks(range(5),['\u76f4\u884c\u6307\u4ee4','\u5de6\u8f6c\u6307\u4ee4','\u53f3\u8f6c\u6307\u4ee4','\u5411\u5de6\u6362\u9053'+chr(10)+'\u6307\u4ee4','\u5411\u53f3\u6362\u9053'+chr(10)+'\u6307\u4ee4']);ax.set_yticks(range(7),[f'\u573a\u666f {i:02d}' for i in range(1,8)])
for i in range(7):
 for j in range(5):ax.text(j,i,['\u65b9\u5411\u63a2\u9488','MTR\u5019\u9009','\u5730\u56fe\u8865\u5145'][matrix[i,j]],ha='center',va='center',fontsize=13,color='#132b40')
ax.set_title('\u6307\u4ee4\u4f18\u5148：\u8def\u7ebf\u6765\u6e90\u4e0e\u76ee\u6807\u68c0\u67e5\u7ed3\u679c（\u4e0d\u662f\u9a7e\u9a76\u6210\u529f\u7387）',fontsize=17,pad=18);fig.tight_layout();fig.savefig(out/'summary.png',dpi=160);plt.close(fig)
page=['<!doctype html><meta charset="utf-8">'+style,'<h1>\u6307\u4ee4\u4f18\u5148 · \u4e03\u573a\u666f\u7ed3\u679c</h1><p>\u4eba\u7684\u6307\u4ee4\u51b3\u5b9a\u52a8\u4f5c\u76ee\u6807；\u5b89\u5168\u68c0\u67e5\u5355\u72ec\u6807\u6ce8，\u4e0d\u518d\u76f4\u63a5\u6321\u6389\u5019\u9009。</p>',
 f'<p><b>35\u6761\u6307\u4ee4：{counts["mtr"]}\u6761\u9009\u5230 MTR \u5019\u9009，{counts["supplement"]}\u6761\u4f7f\u7528\u5730\u56fe\u8865\u5145，{counts["none"]}\u6761\u4ec5\u63d0\u4f9b\u65e0\u9053\u8def\u76ee\u6807\u7684\u5f3a\u5236\u65b9\u5411\u63a2\u9488。</b></p>',
 '<p>35\u6761\u6307\u4ee4\u90fd\u6709\u53ef\u67e5\u770b\u7684\u65b9\u5411\u8f93\u51fa，\u4f46\u53ea\u670927\u6761\u83b7\u5f97\u9053\u8def\u76ee\u6807\u652f\u6301；\u8fd9\u4e0d\u662f35\u6b21\u6210\u529f\u9a7e\u9a76。MTR、\u5730\u56fe\u8865\u5145\u548c\u65b9\u5411\u63a2\u9488\u5206\u522b\u7edf\u8ba1。</p><img src="summary.png">',
 '<p>\u672c\u8f6e“\u76f4\u884c”\u660e\u786e\u6309\u5f53\u524d\u8f66\u5934\u65b9\u5411\u7406\u89e3。“\u6cbf\u5f53\u524d\u9053\u8def\u7ee7\u7eed\u8d70”\u53ef\u80fd\u4f1a\u968f\u9053\u8def\u8f6c\u5f2f，\u662f\u4e0b\u4e00\u9879\u9700\u8981\u5355\u72ec\u63d0\u4f9b\u7684\u6307\u4ee4。</p>']
for s in range(1,8):page.append(f'<section><a href="scene-{s:02d}.html">\u573a\u666f {s:02d}：\u89c6\u9891 + \u4e94\u5f20\u5927\u56fe + \u98ce\u9669 + \u4f60\u7684\u65e7\u5907\u6ce8</a></section>')
page.append('<p class="small">\u5168\u90e8\u4f7f\u7528\u56fa\u5b9a7\u4e2a\u5f00\u53d1\u573a\u666f，\u672a\u8bad\u7ec3\u6a21\u578b；\u6ca1\u6709\u4f7f\u7528\u5f55\u5236\u7684\u771f\u5b9e\u672a\u6765\u6216\u4eba\u5de5\u8bc4\u4ef7\u6765\u9009\u62e9\u8def\u7ebf。\u5730\u56fe\u8865\u5145\u4f7f\u75286\u79d2\u4e94\u6b21\u66f2\u7ebf，\u4fdd\u6301\u8d77\u59cb\u4f4d\u7f6e、\u901f\u5ea6\u548c\u52a0\u901f\u5ea6\u7ea6\u675f，\u98ce\u9669\u53e6\u5916\u68c0\u67e5。\u4e0d\u5b58\u5728\u5bf9\u5e94\u9053\u8def\u76ee\u6807\u65f6\u4fdd\u7559\u5931\u8d25。</p>')
(out/'index.html').write_text('\n'.join(page),encoding='utf-8')
write_json(out/'summary.json',{'counts':counts,'unresolved':missing,'definition':'Target grounding only; not success rate'})
print(json.dumps({'counts':counts,'unresolved':missing},ensure_ascii=False))

