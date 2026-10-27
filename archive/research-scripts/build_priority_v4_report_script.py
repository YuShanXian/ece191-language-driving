from pathlib import Path
root=Path('historical-project')
s=(root/'scripts/report_instruction_priority_v3.py').read_text(encoding='utf-8-sig').replace('instruction-priority-v3','instruction-priority-v4')
s=s.replace("counts={'mtr':0","probe_base=ROOT/'runs/project-v3/forced-direction-probes-v1'\nprobes={(p['scene'],p['command']):p for p in json.loads((probe_base/'results.json').read_text())['results']}\ncounts={'mtr':0")
s=s.replace("  note=reviews[(s-1)*5+j]['reason']",'''  if present and ch.get('tracking'):
   cases=ch['tracking']['cases'];retained=sum(bool(ca.get('target_retained')) for ca in cases)
   worst=max(ca['metrics']['maximum_center_error_m'] for ca in cases)
   parts.append(f'<p><b>\u8f66\u8f86\u6a21\u578b\u8ddf\u8e2a：{retained}/3 \u79cd\u521d\u59cb\u8f6c\u5411\u8bbe\u7f6e\u4ecd\u6ee1\u8db3\u52a8\u4f5c\u76ee\u6807。</b> \u6700\u5927\u4f4d\u7f6e\u504f\u5dee {worst:.2f} \u7c73。</p>')
  if not present:
   probe=probes[(s,j)];retained=sum(ca['geometric_action_retained'] for ca in probe['cases'])
   parts.append(f'<p class="risk"><b>\u53e6\u63d0\u4f9b\u5f3a\u5236\u65b9\u5411\u63a2\u9488：</b>\u53ea\u9a8c\u8bc1\u671d\u6307\u5b9a\u65b9\u5411\u8fd0\u52a8，\u6ca1\u6709\u786e\u8ba4\u5bf9\u5e94\u9053\u8def\u6216\u8f66\u9053。\u5b83\u7531\u7a0b\u5e8f\u751f\u6210，\u4e0d\u662f MTR \u8f93\u51fa。{retained}/3 \u79cd\u521d\u59cb\u8f6c\u5411\u8bbe\u7f6e\u4fdd\u6301\u4e86\u51e0\u4f55\u52a8\u4f5c。</p>')
   parts.append('<p class="small">\u63a2\u9488\u98ce\u9669：'+html.escape('；'.join(risknames.get(k,k) for k in probe['risk_flags']))+'</p>')
  note=reviews[(s-1)*5+j]['reason']''')
s=s.replace('  points=np.vstack(extent);lo=','''  if not present:
   p=local(np.load(probe_base/f'scene-{s:02d}-command-{j}.npz')['points']);extent.append(p)
   ax.plot(p[:,0],p[:,1],c='#a64e9c',lw=3.5,label='\u5f3a\u5236\u65b9\u5411\u63a2\u9488（\u65e0\u9053\u8def\u76ee\u6807）')
  if present:
   simpath=out/f'scene-{s:02d}-command-{j}-steer+0.npz'
   if not simpath.exists():simpath=ROOT/f'runs/project-v3/instruction-priority-v3/tracking/scene-{s:02d}-command-{j}-steer+0.npz'
  else:simpath=probe_base/f'scene-{s:02d}-command-{j}-steer+0.npz'
  if simpath.exists():
   sim=local(np.load(simpath)['center_xy']);extent.append(sim);ax.plot(sim[:,0],sim[:,1],':',c='#c64b30',lw=2,label='\u7b80\u5316\u8f66\u8f86\u6a21\u578b\u5b9e\u9645\u8d70\u51fa\u7684\u7ebf')
  points=np.vstack(extent);lo=''')
s=s.replace("['\u65e0\u76ee\u6807\u8def\u7ebf','MTR\u5019\u9009','\u5730\u56fe\u8865\u5145']","['\u65b9\u5411\u63a2\u9488','MTR\u5019\u9009','\u5730\u56fe\u8865\u5145']")
s=s.replace('\u6761\u5c1a\u672a\u627e\u5230\u76ee\u6807\u8def\u7ebf。','\u6761\u4ec5\u63d0\u4f9b\u65e0\u9053\u8def\u76ee\u6807\u7684\u5f3a\u5236\u65b9\u5411\u63a2\u9488。')
s=s.replace('\u4ee5\u4e0a\u662f\u7a0b\u5e8f\u68c0\u67e5\u7ed3\u679c，\u4e0d\u662f\u4eba\u5de5\u786e\u8ba4\u7684\u6210\u529f\u7387。MTR \u548c\u8865\u5145\u65b9\u6cd5\u5206\u5f00\u7edf\u8ba1。','35\u6761\u6307\u4ee4\u90fd\u6709\u53ef\u67e5\u770b\u7684\u65b9\u5411\u8f93\u51fa，\u4f46\u53ea\u670927\u6761\u83b7\u5f97\u9053\u8def\u76ee\u6807\u652f\u6301；\u8fd9\u4e0d\u662f35\u6b21\u6210\u529f\u9a7e\u9a76。MTR、\u5730\u56fe\u8865\u5145\u548c\u65b9\u5411\u63a2\u9488\u5206\u522b\u7edf\u8ba1。')
(root/'scripts/report_instruction_priority_v4.py').write_text(s,encoding='utf-8')
