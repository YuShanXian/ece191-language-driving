from pathlib import Path
import json,html,hashlib
ROOT=Path('historical-project');scripts=ROOT/'scripts';base=ROOT/'runs/project-v3/instruction-priority-v6';out=base/'human-review';out.mkdir(exist_ok=True)
prior=ROOT/'runs/project-v3/language-choice-v1/report-reviewed/human-review/round-2';reviews=json.loads((prior/'reviews.json').read_text())['reviews'];new=json.loads((base/'results.json').read_text());old=json.loads((prior.parent.parent/'evaluation.json').read_text())
labels=['\u76f4\u884c\u6307\u4ee4','\u5de6\u8f6c\u6307\u4ee4','\u53f3\u8f6c\u6307\u4ee4','\u5411\u5de6\u6362\u9053\u6307\u4ee4','\u5411\u53f3\u6362\u9053\u6307\u4ee4'];rows=[]
for wi,w in enumerate(new['windows']):
 for j,ch in enumerate(w['choices']):
  h=reviews[wi*5+j];oldid=old['windows'][wi]['choices'][j]['choice']['candidate'];present=ch['status']=='destination_grounded_offline';note='\u5f85\u91cd\u65b0\u8bc4\u5ba1：\u8def\u7ebf\u6216\u89c4\u5219\u5df2\u53d8\u5316，\u4e0d\u80fd\u6cbf\u7528\u65e7\u7ed3\u8bba。'
  if not present:note='\u65e7\u8bc4\u5ba1\u8ba4\u53ef\u4e0d\u8f93\u51fa\u8def\u7ebf：\u672c\u8f6e\u53ef\u6682\u5217\u5408\u7406\u62d2\u7edd，\u4ecd\u8bf7\u91cd\u65b0\u786e\u8ba4。' if h['verdict']=='success' and oldid is None else '\u65e7\u8bc4\u5ba1\u8ba4\u4e3a\u5e94\u8be5\u80fd\u505a：\u672c\u8f6e\u4ecd\u6ca1\u627e\u5230\u8def\u7ebf，\u6682\u5217\u5931\u8d25。'
  elif oldid is None and h['verdict']=='success':note='\u91cd\u70b9\u590d\u67e5：\u65e7\u8bc4\u5ba1\u8ba4\u53ef\u4e0d\u8f93\u51fa\u8def\u7ebf，\u65b0\u7248\u53cd\u800c\u8f93\u51fa\u4e86\u8def\u7ebf，\u53ef\u80fd\u662f\u9519\u8bef\u6267\u884c。'
  if present:
   source='MTR \u9884\u6d4b\u7684\u8def\u7ebf（\u7ecf\u8fc7\u5e73\u6ed1）' if ch['source']=='MTR_refined' else '\u7a0b\u5e8f\u6839\u636e\u5730\u56fe\u53e6\u884c\u751f\u6210\u7684\u8def\u7ebf，\u4e0d\u662f MTR \u8f93\u51fa'
   behavior='\u672c\u8f6e\u8f93\u51fa：'+source+'。'
   if ch.get('navigation',{}).get('mode')=='follow_road_fallback':behavior+='\u4e0d\u80fd\u4fdd\u6301\u8f66\u5934\u65b9\u5411，\u6539\u4e3a\u6cbf\u9053\u8def\u5f2f\u66f2\u7ee7\u7eed\u884c\u9a76。'
  else:behavior='\u672c\u8f6e\u8f93\u51fa：\u6ca1\u6709\u63d0\u4f9b\u53ef\u9009\u9053\u8def\u8def\u7ebf。\u6b64\u524d\u7684\u7d2b\u8272\u65b9\u5411\u6d4b\u8bd5\u7ebf\u4e0d\u4f5c\u4e3a\u6267\u884c\u8def\u7ebf，\u4e5f\u4e0d\u4f5c\u4e3a\u6210\u529f\u4f9d\u636e。'
  rows.append({'scene':wi+1,'command':j,'instruction':labels[j],'behavior':behavior,'previous_verdict':h['verdict'],'previous_reason':h['reason'],'review_hint':note,'previous_candidate':oldid,'current_has_road_route':present})
(out/'comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
s=(prior/'index.html').read_text();s=s.replace('\u7b2c2\u8f6e','\u65b0\u7248').replace('\u7b2c 2 \u8f6e','\u65b0\u7248').replace('round-2','v6-review').replace('human-review / v6-review / reviews.json','instruction-priority-v6 / human-review / reviews.json')
s=s.replace('let state,sources,scene=1', 'const comparisons='+json.dumps(rows,ensure_ascii=False)+';\nconst esc=s=>String(s).replace(/[&<>"\x27]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\\\"":"&quot;","\x27":"&#39;"}[c]||c));\nlet state,sources,scene=1')
s=s.replace("let r=state.reviews[(scene-1)*5+c];", "let r=state.reviews[(scene-1)*5+c];let info=comparisons[(scene-1)*5+c];")
s=s.replace("+'</span></h3><img class=", "+'</span></h3><p><b>'+esc(info.behavior)+'</b></p><p>'+esc(info.review_hint)+'</p><p class=\"tip\">\u65e7\u8bc4\u5ba1：'+esc(({success:'\u6210\u529f',fail:'\u5931\u8d25',uncertain:'\u4e0d\u786e\u5b9a'})[info.previous_verdict])+'；\u65e7\u5907\u6ce8：'+esc(info.previous_reason||'\u672a\u586b\u5199\u7406\u7531')+'</p><img class=")
s=s.replace("function progress(){let n=state.reviews.filter(r=>r.verdict).length;document.getElementById('progress').textContent='\u5df2\u5224\u65ad '+n+' / 35';}","function progress(){let n=state.reviews.filter(r=>r.verdict).length,ok=state.reviews.filter(r=>r.verdict==='success').length,no=state.reviews.filter(r=>r.verdict==='fail').length,u=state.reviews.filter(r=>r.verdict==='uncertain').length;document.getElementById('progress').textContent='\u5df2\u5224\u65ad '+n+'/35 · \u6210\u529f '+ok+' · \u5931\u8d25 '+no+' · \u4e0d\u786e\u5b9a '+u+' · \u660e\u786e\u5224\u65ad\u4e2d\u7684\u6210\u529f\u7387 '+(ok+no?(100*ok/(ok+no)).toFixed(1)+'%':'\u5f85\u8bc4\u5ba1')+'（\u5206\u6bcd '+(ok+no)+'）';}")
s=s.replace('\u8bc4\u4ef7\u7684\u662f“\u8fd9\u6761\u6307\u4ee4\u4e0b\u7a0b\u5e8f\u7684\u8868\u73b0”。','\u6210\u529f＝\u6b63\u786e\u6267\u884c，\u6216\u52a8\u4f5c\u6ca1\u6709\u5bf9\u5e94\u9053\u8def\u65f6\u6b63\u786e\u62d2\u7edd；\u5931\u8d25＝\u6267\u884c\u9519\u8bef，\u6216\u672c\u6765\u80fd\u505a\u5374\u6ca1\u505a。\u5b89\u5168\u60c5\u51b5\u5355\u72ec\u586b\u5199，\u4e0d\u81ea\u52a8\u6539\u53d8\u52a8\u4f5c\u662f\u5426\u5b8c\u6210\u7684\u5224\u65ad。\u672c\u8f6e\u4e0d\u91c7\u7528\u65e0\u9053\u8def\u4f9d\u636e\u7684\u65b9\u5411\u6d4b\u8bd5\u7ebf。')
(out/'index.html').write_text(s,encoding='utf-8')
s=(scripts/'serve_human_review.py').read_text();s=s.replace('OUT=BASE/"round-2"','OUT=ROOT/"runs/project-v3/instruction-priority-v6/human-review"').replace('"round":2','"round":3').replace('data["round"]!=2','data["round"]!=3').replace('round-2','v6-review').replace('8768','8769').replace('p=BASE/f"scene-{int(s):02d}-command-{c}.png"','p=OUT/f"scene-{int(s):02d}-command-{c}.png"\n   if not p.exists():p=OUT.parent/f"scene-{int(s):02d}-command-{c}.png"')
(scripts/'serve_v6_review.py').write_text(s,encoding='utf-8')
# Preserve original reviews; initialize a genuinely blank new round only once.
state=out/'reviews.json'
if not state.exists():state.write_text(json.dumps({'round':3,'reviews':[{'scene':i,'command':j,'verdict':'','safety':'','reason':''} for i in range(1,8) for j in range(5)]},ensure_ascii=False,indent=2),encoding='utf-8')
print('Comparison and blank review created. Old review hash:',hashlib.sha256((prior/'reviews.json').read_bytes()).hexdigest())
