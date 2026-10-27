import json,html
from mtr_project.paths import ROOT,write_json
base=ROOT/'runs/project-v3/instruction-priority-v6'
audit=json.loads((base/'context-risk.json').read_text())
labels=['\u76f4\u884c\u6307\u4ee4','\u5de6\u8f6c\u6307\u4ee4','\u53f3\u8f6c\u6307\u4ee4','\u5411\u5de6\u6362\u9053\u6307\u4ee4','\u5411\u53f3\u6362\u9053\u6307\u4ee4']
english=['Go straight','Turn left','Turn right','Change lanes to the left','Change lanes to the right']
for scene in range(1,8):
 p=base/f'scene-{scene:02d}.html';s=p.read_text()
 if '<!-- contextual-risk-v1 -->' in s:continue
 for r in [r for r in audit['results'] if r['scene']==scene]:
  j=r['command'];notes=[]
  if r['signal_association_ambiguous']:notes.append('\u4ea4\u901a\u706f\u5173\u8054\u6709\u6b67\u4e49：\u8def\u7ebf\u540c\u65f6\u7ecf\u8fc7\u5f53\u524d\u7ea2\u706f\u4e0e\u7eff\u706f\u7684\u8fde\u63a5\u533a\u57df，\u9700\u8981\u7ed3\u5408\u89c6\u9891\u786e\u8ba4\u5bf9\u5e94\u4fe1\u53f7。')
  elif 'current_red_signal_on_overlapped_connector' in r['context_risk_flags']:notes.append('\u7ea2\u706f\u98ce\u9669：\u8def\u7ebf\u7ecf\u8fc7\u7684\u8fde\u63a5\u533a\u57df，\u5728\u5f53\u524d\u6570\u636e\u5e93\u8bb0\u5f55\u4e2d\u4e3a\u7ea2\u706f。')
  elif r['database_signal_rows']==0:notes.append('\u5f53\u524d\u6570\u636e\u5e93\u6ca1\u6709\u4ea4\u901a\u706f\u8bb0\u5f55，\u7ea2\u7eff\u706f\u72b6\u6001\u672a\u77e5。')
  else:notes.append('\u6ca1\u6709\u5173\u8054\u5230\u5f53\u524d\u7ea2\u706f\u8bb0\u5f55；\u8fd9\u4e0d\u4ee3\u8868\u5df2\u5b8c\u6210\u4ea4\u901a\u89c4\u5219\u68c0\u67e5。')
  if 'sustained_opposite_lane_direction' in r['context_risk_flags']:notes.append('\u65b9\u5411\u98ce\u9669：\u90e8\u5206\u8def\u7ebf\u4e0e\u5730\u56fe\u8f66\u9053\u884c\u9a76\u65b9\u5411\u76f8\u53cd。')
  text='<p class="risk">'+' '.join(notes)+'</p><p class="small">\u4ea4\u901a\u706f\u53ea\u4f7f\u7528\u5f53\u524d\u65f6\u523b\u8bb0\u5f55，\u4e0d\u9884\u6d4b\u8f66\u8f86\u5230\u8fbe\u65f6\u7684\u706f\u8272；\u4ea4\u53c9\u533a\u57df\u7684\u4fe1\u53f7\u5bf9\u5e94\u53ef\u80fd\u4e0d\u552f\u4e00。</p>'
  anchor=f'<h2>{labels[j]} · {english[j]}</h2>'
  assert anchor in s
  s=s.replace(anchor,anchor+text)
 s=s.replace('\u7ea2\u7eff\u706f、\u8f66\u9053\u7ebf\u5408\u6cd5\u6027\u5c1a\u672a\u81ea\u52a8\u68c0\u67e5','\u5f53\u524d\u7ea2\u7eff\u706f\u8bb0\u5f55\u5df2\u5355\u5217；\u8f66\u9053\u7ebf\u5408\u6cd5\u6027\u5c1a\u672a\u81ea\u52a8\u68c0\u67e5')
 p.write_text(s+'\n<!-- contextual-risk-v1 -->',encoding='utf-8')
p=base/'index.html';s=p.read_text();s=s.replace('<h1>\u6307\u4ee4\u4f18\u5148 · \u4e03\u573a\u666f\u7ed3\u679c</h1>','<h1>\u6307\u4ee4\u4f18\u5148 · \u4e03\u573a\u666f\u7ed3\u679c</h1><p>\u5df2\u8865\u5145\u5f53\u524d\u4ea4\u901a\u706f\u8bb0\u5f55\u4e0e\u9006\u5411\u884c\u9a76\u98ce\u9669。\u98ce\u9669\u5355\u72ec\u663e\u793a，\u4e0d\u963b\u6b62\u79bb\u7ebf\u65b9\u5411\u6d4b\u8bd5。</p>');p.write_text(s,encoding='utf-8')
print('Added context risk evidence to 35 command cards')
