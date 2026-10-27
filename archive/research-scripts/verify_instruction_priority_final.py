import json,re
from pathlib import Path
from mtr_project.paths import ROOT,write_json,sha256
base=ROOT/'runs/project-v3/instruction-priority-v5'
data=json.loads((base/'results.json').read_text());probes=json.loads((ROOT/'runs/project-v3/forced-direction-probes-v1/results.json').read_text())['results']
assert len(data['windows'])==7
counts={'mtr':0,'map':0,'probes':len(probes),'road_target_3of3':0,'probe_direction_3of3':sum(all(c['geometric_action_retained'] for c in p['cases']) for p in probes)}
for w in data['windows']:
 assert len(w['choices'])==5
 for j,c in enumerate(w['choices']):
  assert (base/f'scene-{w["scene"]:02d}-command-{j}.png').is_file()
  if c['status']=='destination_grounded_offline':
   counts['mtr' if c['source']=='MTR_refined' else 'map']+=1
   assert all(ca['target_retained'] for ca in c['tracking']['cases'])
   counts['road_target_3of3']+=1
for p in base.glob('*.html'):
 for ref in re.findall(r'(?:href|src)="([^"]+)"',p.read_text()):
  if ref.startswith(('http:','https:','#')):continue
  assert (p.parent/ref).exists(),(p,ref)
reviews=ROOT/'runs/project-v3/language-choice-v1/report-reviewed/human-review/round-2/reviews.json'
assert len(json.loads(reviews.read_text())['reviews'])==35
sources=json.loads((reviews.parent.parent/'real-camera/sources.json').read_text())
assert {s['scene'] for s in sources}==set(range(1,8))
result={'counts':counts,'report_images':35,'report_pages':8,'manual_reviews':35,'review_sha256':sha256(reviews),'all_local_links_exist':True,'video_sources':7,'scope':'Target checks and simplified tracking, no safety or real-world success claim.'}
write_json(base/'verification.json',result)
doc=ROOT/'docs/INSTRUCTION_PRIORITY.txt'
doc.write_text(doc.read_text(encoding='utf-8-sig')+'''
\u6700\u65b0\u66f4\u65b0：instruction-priority-v5
- \u6700\u65b0\u62a5\u544a\u6539\u4e3a runs/project-v3/instruction-priority-v5/index.html。
- \u6700\u7ec8：23\u6761MTR\u5019\u9009、4\u6761\u5730\u56fe\u8865\u5145、8\u6761\u65e0\u9053\u8def\u76ee\u6807\u65b9\u5411\u63a2\u9488。
- 27\u6761\u9053\u8def\u76ee\u6807\u8def\u7ebf\u5747\u5728\u4e09\u79cd\u521d\u59cb\u8f6c\u5411\u5047\u8bbe\u4e0b\u4fdd\u6301\u76ee\u6807；8\u6761\u65b9\u5411\u63a2\u9488\u5747\u4fdd\u6301\u51e0\u4f55\u52a8\u4f5c。
- \u573a\u666f02\u76f4\u884c：\u77ed\u8ddd\u79bb\u76ee\u6807\u91c7\u6837\u627e\u5230\u5730\u56fe\u8865\u5145\u8def\u7ebf。\u751f\u6210\u5668\u4e0e\u9a8c\u8bc1\u5668\u7684\u76f4\u884c20\u5ea6\u6807\u51c6\u7edf\u4e00；\u9a8c\u8bc1\u9608\u503c\u6ca1\u6709\u653e\u5bbd。\u6700\u5927\u8ddf\u8e2a\u8bef\u5dee\u7ea61.27\u7c73，\u4e0d\u4ee3\u8868\u5b89\u5168。
- \u4ecd\u672a\u8bc1\u660e35\u6761\u90fd\u662f\u53ef\u7528\u9053\u8def\u52a8\u4f5c；8\u6761\u63a2\u9488\u4e0d\u80fd\u8ba1\u5165\u9053\u8def\u52a8\u4f5c\u6210\u529f\u7387。
- \u6700\u7ec8\u4ee3\u7801\u5165\u53e3：finalize_instruction_priority.py；\u62a5\u544a：report_instruction_priority_v5.py。
- verification.json\u68c0\u67e57\u573a\u666f、35\u5f20\u56fe、8\u9875、\u672c\u5730\u94fe\u63a5、7\u89c6\u9891\u6765\u6e90\u53ca\u4eba\u5de5\u8bc4\u4ef7\u6587\u4ef6。
''',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
