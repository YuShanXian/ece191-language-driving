import json,pickle,html,re,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph
base=ROOT/'runs/project-v3/instruction-priority-v7';prior=ROOT/'runs/project-v3/instruction-priority-v6';out=base/'human-review';out.mkdir(exist_ok=True)
data=json.loads((base/'results.json').read_text());reviews=json.loads((prior/'human-review/reviews.json').read_text())['reviews'];labels=['\u76f4\u884c\u6307\u4ee4','\u5de6\u8f6c\u6307\u4ee4','\u53f3\u8f6c\u6307\u4ee4','\u5411\u5de6\u6362\u9053\u6307\u4ee4','\u5411\u53f3\u6362\u9053\u6307\u4ee4'];rows=[]
font_manager.fontManager.addfont('/mnt/c/Windows/Fonts/msyh.ttc');plt.rcParams['font.family']=font_manager.FontProperties(fname='/mnt/c/Windows/Fonts/msyh.ttc').get_name();plt.rcParams['axes.unicode_minus']=False
for w in data['windows']:
 s=w['scene'];src=w['source_window'];run=ROOT/'runs'/src['run'];sample=ROOT/'samples'/src['sample'];conv=json.loads((sample/'conversion.json').read_text());g=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);center=np.load(run/'internal_0000.npz')['center'];saved=np.load(base/f'scene-{s:02d}-selected.npz');previous=np.load(prior/f'scene-{s:02d}-selected.npz');ego=pickle.load(open(sample/conv['scenario'],'rb'))['tracks']['ego']['state'];h=center[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]]);local=lambda p:(np.asarray(p)[...,:2]-center[:2])@rot
 for j,ch in enumerate(w['choices']):
  human=reviews[(s-1)*5+j];has=f'command_{j}' in saved;repair=ch.get('repair') if isinstance(ch.get('repair'),dict) else None;horizon=(len(saved[f'command_{j}'])-1)/10 if has else 0
  if not has:behavior='\u6ca1\u6709\u63d0\u4f9b\u8be5\u52a8\u4f5c\u8def\u7ebf，\u8bf7\u5224\u65ad\u4e0d\u6267\u884c\u662f\u5426\u5408\u7406。'
  elif ch.get('effective_action')=='continue_without_requested_lane_change':behavior='\u4e0d\u518d\u6362\u9053，\u663e\u793a\u7ee7\u7eed\u884c\u9a76\u7684\u8def\u7ebf；\u8bf7\u5224\u65ad\u8fd9\u662f\u5426\u7b26\u5408\u573a\u666f。'
  else:behavior='\u5df2\u63d0\u4f9b'+('MTR\u9884\u6d4b\u8def\u7ebf\u7684\u5e73\u6ed1\u7248\u672c' if ch['source']=='MTR_refined' else '\u7a0b\u5e8f\u6309\u5730\u56fe\u751f\u6210\u7684\u8865\u5145\u8def\u7ebf（\u4e0d\u662fMTR\u8f93\u51fa）')+f'，\u65f6\u957f{horizon:g}\u79d2。'
  if horizon>6:behavior+='\u8fd9\u662f\u5ef6\u957f\u65f6\u95f4\u540e\u7684\u8ba1\u5212，\u4e0d\u80fd\u7b976\u79d2\u5185\u5b8c\u6210\u52a8\u4f5c。'
  reason=repair['reason'] if repair else '\u672c\u8f6e\u4fdd\u7559\u4e0a\u4e00\u7248\u8def\u7ebf，\u8bf7\u68c0\u67e5\u662f\u5426\u4ecd\u8ba4\u53ef。'
  cases=(ch.get('tracking') or {}).get('cases',[]);count=sum(x['target_retained'] for x in cases)
  if has and cases:reason+=f' \u7b80\u5316\u8f66\u8f86\u6a21\u578b：{count}/{len(cases)}\u79cd\u521d\u59cb\u8f6c\u5411\u8bbe\u7f6e\u4fdd\u6301\u76ee\u6807。'
  if ch.get('risk_flags'):reason+=' \u98ce\u9669\u63d0\u793a：'+', '.join({'road_footprint':'\u8f66\u8eab\u53ef\u80fd\u8d8a\u51fa\u9053\u8def','motion':'\u901f\u5ea6\u6216\u52a0\u901f\u5ea6\u7b49\u6307\u6807\u8d85\u9650','constant_velocity_collision':'\u53ef\u80fd\u4e0e\u5176\u4ed6\u8f66\u8f86\u51b2\u7a81','ambiguous_start_lane':'\u8d77\u59cb\u8f66\u9053\u4e0d\u786e\u5b9a','observed_start_road_route':'\u9053\u8def\u5168\u8fc7\u7a0b\u8fde\u63a5\u672a\u786e\u8ba4','refinement_deviation':'\u5e73\u6ed1\u6539\u52a8\u8f83\u5927'}.get(x,x) for x in ch['risk_flags'])+'。'
  rows.append({'scene':s,'command':j,'instruction':labels[j],'behavior':behavior,'previous_verdict':human['verdict'],'previous_reason':human['reason'],'review_hint':reason,'current_has_road_route':has,'horizon_s':horizon})
  fig,ax=plt.subplots(figsize=(11,8.5));extent=[np.array([[0,0],[35,0]])]
  for k,n in enumerate(g.nodes.values()):
   p=local(n.baseline.coords);ax.plot(p[:,0],p[:,1],color='#d2d8de',lw=1,label='\u5730\u56fe\u4e2d\u5fc3\u7ebf（\u4e0d\u662f\u5730\u9762\u6807\u7ebf）' if k==0 else None)
  if has:
   target=ch['features']['target'];keys=target.get('visited_target_nodes',[target.get('node')])
   for k,key in enumerate(keys):
    if key in g.nodes:
     p=local(g.nodes[key].baseline.coords);ax.plot(p[:,0],p[:,1],color='#52a085',lw=2,label='\u76ee\u6807\u9053\u8def\u4e2d\u5fc3\u7ebf' if k==0 else None)
   p=local(saved[f'command_{j}']);extent.append(p);ax.plot(p[:,0],p[:,1],color='#2268b1',lw=3.5,label=f'\u672c\u8f6e\u8def\u7ebf（{horizon:g}\u79d2）')
   if repair and f'command_{j}' in previous:
    p=local(previous[f'command_{j}']);extent.append(p);ax.plot(p[:,0],p[:,1],'--',color='#d28b32',lw=2,label='\u4f60\u4e0a\u4e00\u8f6e\u770b\u5230\u7684\u8def\u7ebf')
   ref=ch.get('tracking_reference',{});rs=ref.get('scene',s);rj=ref.get('command',j)
   paths=[base/f'scene-{s:02d}-command-{j}-steer+0.npz'] if not ref else []
   paths += [ROOT/f'runs/project-v3/{v}/scene-{rs:02d}-command-{rj}-steer+0.npz' for v in ['instruction-priority-v6','instruction-priority-v5','instruction-priority-v4','instruction-priority-v3/tracking']]
   sim=next((p for p in paths if p.exists()),None)
   if sim is not None:
    p=local(np.load(sim)['center_xy']);extent.append(p);ax.plot(p[:,0],p[:,1],':',color='#c45139',lw=2,label='\u7b80\u5316\u8f66\u8f86\u6a21\u578b\u8d70\u51fa\u7684\u8def\u7ebf')
  p=local(ego['position'][:21,:2]);extent.append(p);ax.plot(p[:,0],p[:,1],color='#222',lw=2.5,label='\u8fc7\u53bb2\u79d2\u5b9e\u9645\u8def\u7ebf');ax.scatter(0,0,c='#222',s=60,label='\u5f53\u524d\u4f4d\u7f6e');allp=np.vstack(extent);low=allp.min(0)-12;high=allp.max(0)+12;span=np.maximum(high-low,50);mid=(high+low)/2;ax.set_xlim(mid[0]-span[0]/2,mid[0]+span[0]/2);ax.set_ylim(mid[1]-span[1]/2,mid[1]+span[1]/2);ax.set_aspect('equal');ax.grid(alpha=.15);ax.legend(fontsize=10);ax.set_xlabel('\u6cbf\u5f53\u524d\u8f66\u5934\u65b9\u5411\u5411\u524d（\u7c73）');ax.set_ylabel('\u5411\u5de6（\u7c73）');title='\u6ca1\u6709\u63d0\u4f9b\u8be5\u52a8\u4f5c\u8def\u7ebf：\u8bf7\u5224\u65ad\u662f\u5426\u5e94\u8be5\u62d2\u7edd' if not has else ('\u4e0d\u6267\u884c\u6362\u9053，\u6539\u4e3a\u7ee7\u7eed\u884c\u9a76' if ch.get('effective_action')=='continue_without_requested_lane_change' else f'\u672c\u8f6e\u8def\u7ebf：{horizon:g}\u79d2，\u7b49\u5f85\u4eba\u5de5\u5224\u65ad')
  ax.set_title(f'\u573a\u666f {s:02d} · {labels[j]}\n{title}',fontsize=17);fig.tight_layout();fig.savefig(base/f'scene-{s:02d}-command-{j}.png',dpi=150,bbox_inches="tight");plt.close(fig)
 print('Rendered scene',s,flush=True)
write_json(out/'comparison.json',rows)
s=(prior/'human-review/index.html').read_text();s=re.sub(r'const comparisons=.*?;\nconst esc=',lambda m:'const comparisons='+json.dumps(rows,ensure_ascii=False)+';\nconst esc=',s,flags=re.S);s=s.replace('v6-review','v7-review').replace('instruction-priority-v6','instruction-priority-v7').replace('MTR \u8def\u7ebf\u9009\u62e9 · \u65b0\u7248\u4eba\u5de5\u8bc4\u5ba1','MTR \u8def\u7ebf\u9009\u62e9 · \u4fee\u6b63\u540e\u4eba\u5de5\u8bc4\u5ba1');s=s.replace('\u5148\u770b\u573a\u666f\u89c6\u9891，\u518d\u770b\u4e94\u6761\u6307\u4ee4\u7684\u8def\u7ebf\u56fe，\u5728\u56fe\u4e0b\u5199\u4f60\u7684\u5224\u65ad。','\u4e0a\u4e00\u8f6e：27\u6210\u529f、7\u5931\u8d25、1\u4e0d\u786e\u5b9a。\u672c\u8f6e\u4fee\u6b639\u6761（\u542b\u8865\u5145\u7684\u7ee7\u7eed\u884c\u9a76\u8def\u7ebf），\u8bf7\u91cd\u65b0\u5224\u65ad\u5168\u90e835\u6761。\u573a\u666f05\u53f3\u8f6c\u82e5\u663e\u793a12\u79d2，\u5e94\u6309\u5ef6\u957f\u8ba1\u5212\u8bc4\u4ef7，\u4e0d\u8ba1\u4f5c6\u79d2\u5b8c\u6210。');(out/'index.html').write_text(s.replace('</html>','<script src="/target-picker.js"></script></html>') if (out/'target-picker.js').exists() else s,encoding='utf-8')
if not (out/'reviews.json').exists():write_json(out/'reviews.json',{'round':4,'reviews':[{'scene':i,'command':j,'verdict':'','safety':'','reason':''} for i in range(1,8) for j in range(5)]})
p=ROOT/'scripts/serve_v6_review.py';s=p.read_text().replace('instruction-priority-v6','instruction-priority-v7').replace('v6-review','v7-review').replace('8769','8770').replace('"round":3','"round":4').replace('data["round"]!=3','data["round"]!=4');(ROOT/'scripts/serve_v7_review.py').write_text(s,encoding='utf-8')
write_json(base/'report-status.json',{'human_confirmation':'pending','prior_success':27,'prior_fail':7,'prior_uncertain':1,'changed_commands':9,'new_success_rate':None,'note':'Targets explicitly informed by human development reviews; not independent evaluation. No MTR weights retrained.'})


