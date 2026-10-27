import json,html,copy
from pathlib import Path
from benchmark_providers import OUT,CASES,summarize,check
results=json.loads((OUT/'results.json').read_text(encoding='utf-8'));rows=summarize(results)
decision=json.loads((OUT/'decision.json').read_text(encoding='utf-8')) if (OUT/'decision.json').exists() else {}
def h(s):return html.escape(str(s))
body='<h1>\u54ea\u4e2a\u6a21\u578b\u66f4\u9002\u5408\u9a7e\u9a76\u6307\u4ee4\u89e3\u6790？</h1>'
if decision:body+=f'<div class="conclusion"><b>\u672c\u8f6e\u9009\u62e9：{h(decision["default"])}。</b><p>\u5148\u8981\u6c42\u5168\u90e8 16 \u7c7b\u6d4b\u8bd5\u901a\u8fc7\u4e24\u8f6e，\u518d\u9009\u5b8c\u6574\u89e3\u6790\u8017\u65f6\u4e2d\u4f4d\u6570\u6700\u4f4e\u7684\u6a21\u578b。Demo \u4e0b\u62c9\u83dc\u5355\u4e2d\u4fdd\u7559\u901a\u8fc7\u590d\u6d4b\u7684\u5feb\u6a21\u578b。</p></div>'
else:body+='<p>\u6d4b\u8bd5\u4ecd\u5728\u8fdb\u884c，\u5f53\u524d\u7ed3\u679c\u4e0d\u80fd\u4f5c\u4e3a\u6700\u7ec8\u6392\u540d。</p>'
body+='<h2>\u8fd9\u6b21\u6d4b\u7684\u662f\u4ec0\u4e48</h2><p>\u8f93\u5165\u4e00\u53e5\u9a7e\u9a76\u6307\u4ee4，\u6a21\u578b\u628a\u5b83\u8f6c\u6362\u6210\u7a0b\u5e8f\u80fd\u6267\u884c\u7684\u52a8\u4f5c、\u8ddd\u79bb、\u901f\u5ea6\u548c\u5148\u540e\u987a\u5e8f。\u8fd9\u91cc\u6d4b\u7684\u662f<strong>\u8bed\u8a00\u7406\u89e3</strong>，\u6ca1\u6709\u7528\u5730\u56fe\u8f68\u8ff9\u7684\u597d\u574f\u7ed9\u6a21\u578b\u6253\u5206。</p><p>\u8ba1\u65f6\u4ece\u542f\u52a8\u540e\u53f0 CLI \u5230\u6536\u5230\u5b8c\u6574\u56de\u7b54，\u5305\u542b\u767b\u5f55\u72b6\u6001\u8bfb\u53d6、\u7f51\u7edc、\u6a21\u578b\u601d\u8003\u548c\u6587\u5b57\u8f93\u51fa，\u4e0d\u5305\u542b\u5730\u56fe\u89c4\u5212。\u6240\u6709\u6a21\u578b\u4f7f\u7528\u540c\u4e00\u4efd\u63d0\u793a\u8bcd\u548c JSON \u683c\u5f0f。\u4e3b\u6d4b\u8bd5\u6309\u968f\u673a\u987a\u5e8f\u9010\u4e2a\u8c03\u7528；\u5b89\u88c5\u671f\u95f4\u53e6\u6709\u5c11\u91cf\u63a5\u5165\u9a8c\u8bc1\u8c03\u7528，\u590d\u6d4b\u9636\u6bb5\u4e32\u884c\u6267\u884c。</p>'
body+='<p><b>Gemini Flash-Lite \u672a\u53d6\u5f97\u540e\u53f0\u6d4b\u8bd5\u6210\u7ee9：</b>\u65e7 Gemini CLI \u670d\u52a1\u7aef\u62d2\u7edd\u4e2a\u4eba\u8d26\u53f7\u5e76\u8981\u6c42\u8fc1\u79fb；\u8fc1\u79fb\u540e\u7684\u8d26\u53f7\u5217\u8868\u53ea\u5f00\u653e Gemini 3.8 Flash。\u56e0\u6b64\u6d4b\u8bd5\u7684\u662f\u660e\u786e\u6807\u6ce8\u7684 3.8 Flash Low，\u4e0d\u80fd\u7528\u5b83\u4ee3\u66ff Flash-Lite \u7684\u7ed3\u8bba。</p>'
body+='<h2>\u5b9e\u6d4b\u7ed3\u679c</h2><p>\u4e25\u683c\u901a\u8fc7\u8981\u6c42\u56de\u7b54\u80fd\u76f4\u63a5\u4f9b\u7a0b\u5e8f\u4f7f\u7528。\u7406\u89e3\u6b63\u786e\u53e6\u7b97：\u4f8b\u5982\u5df2\u7ecf\u8981\u6c42\u5230\u70b9\u505c\u8f66、\u53c8\u91cd\u590d\u591a\u5199\u4e00\u6b21\u505c\u8f66，\u5c5e\u4e8e\u683c\u5f0f\u95ee\u9898；\u6b63\u786e\u8bc6\u522b\u5426\u5b9a\u53e5\u4f46\u6f0f\u5199“\u672a\u6267\u884c”\u72b6\u6001\u4e5f\u4e0d\u7b97\u7406\u89e3\u9519\u8bef。\u83dc\u5355\u91c7\u7528\u66f4\u4e25\u683c\u7684\u6807\u51c6。\u8c03\u7528\u5931\u8d25\u5355\u72ec\u5217\u51fa。\u901f\u5ea6\u7edf\u8ba1\u53ea\u4f7f\u7528\u6210\u529f\u8fd4\u56de\u7684\u8c03\u7528；\u6709\u5931\u8d25\u7684\u6a21\u578b\u4e0d\u80fd\u4ec5\u51ed\u8f83\u4f4e\u7684\u4e2d\u4f4d\u6570\u83b7\u9009。P90 \u8868\u793a\u4e5d\u6210\u5df2\u8fd4\u56de\u8bf7\u6c42\u5728\u8fd9\u4e2a\u65f6\u95f4\u5185\u5b8c\u6210。\u4e0d\u540c\u6d4b\u8bd5\u6b21\u6570\u662f\u56e0\u4e3a\u4f18\u80dc\u6a21\u578b\u591a\u505a\u4e86\u4e00\u8f6e\u590d\u6d4b。</p><table><tr><th>\u6a21\u578b</th><th>\u7406\u89e3\u6b63\u786e/\u56de\u7b54\u6570</th><th>\u4e25\u683c\u901a\u8fc7/\u603b\u6d4b\u8bd5</th><th>\u8c03\u7528\u5931\u8d25</th><th>\u4e2d\u4f4d\u6570</th><th>P90</th></tr>'
def semantic_pass(r):
 if r.get('transport_error'):return False
 c=next(c for c in CASES if c[0]==r['case']);p=copy.deepcopy(r['parsed'])
 if c[3].get('no_action') and not p['stages']:return True
 s=p['stages']
 if len(s)>1 and s[-1]['action']=='stop' and s[-2]['stop_at_end']:
  p['stages']=s[:-1]
 return not check(p,c)
for r in rows:
 completed=r['total']-r['errors'];semantic=sum(semantic_pass(x) for x in results if x['model']==r['model']);body+=f'<tr><td>{h(r["model"])}</td><td>{semantic}/{completed}</td><td>{r["passed"]}/{r["total"]}</td><td>{r["errors"]}</td><td>{r["median"]} \u79d2</td><td>{r["p90"]} \u79d2</td></tr>'
body+='</table><h2>\u6bcf\u79cd\u6307\u4ee4\u6d4b\u4ec0\u4e48</h2><table><tr><th>\u6d4b\u8bd5</th><th>\u8f93\u5165\u6307\u4ee4</th></tr>'
for c in CASES:body+=f'<tr><td>{h(c[0])}</td><td>{h(c[1])}</td></tr>'
body+='</table><h2>\u672a\u901a\u8fc7\u7684\u5177\u4f53\u7b54\u6848</h2>'
for r in results:
 if r['passed']:continue
 errors='\u8c03\u7528\u8d85\u65f6\u6216\u670d\u52a1\u9519\u8bef，\u672a\u5f97\u5230\u53ef\u8bc4\u5206\u7b54\u6848。' if r.get('transport_error') else '; '.join(r['errors'])
 body+=f'<details><summary>{h(r["model"])} · {h(r["case"])} · \u7b2c {r.get("repeat",0)+1} \u8f6e</summary><p>{h(errors)}</p><pre>{h(json.dumps(r.get("parsed",{}),ensure_ascii=False,indent=2))}</pre></details>'
body+='<p>\u8fd9\u662f\u5c0f\u89c4\u6a21\u5de5\u7a0b\u7b5b\u9009，100% \u6307\u672c\u6d4b\u8bd5\u96c6\u5168\u90e8\u901a\u8fc7，\u4e0d\u4ee3\u8868\u4efb\u610f\u6307\u4ee4\u90fd\u80fd\u6b63\u786e\u7406\u89e3。\u539f\u59cb\u56de\u7b54、\u6bcf\u6b21\u8017\u65f6\u548c\u6d4b\u8bd5\u89c4\u5219\u5747\u4fdd\u5b58\u5728\u672c\u6587\u4ef6\u5939。</p>'
(OUT/'report.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>\u6a21\u578b\u540e\u53f0\u5b9e\u6d4b</title><style>body{font:18px/1.6 Segoe UI,Microsoft YaHei;max-width:1150px;margin:40px auto;padding:0 24px;color:#17344b}h1{font-size:32px}h2{margin-top:36px}td,th{padding:12px;border-bottom:1px solid #d8e2e8;text-align:left}table{width:100%;border-collapse:collapse}.conclusion{padding:24px;background:#e6f4ef;border-radius:12px}pre{white-space:pre-wrap;font-size:14px}details{padding:10px;background:#f4f6f8;margin:8px 0}</style>'+body+'</html>',encoding='utf-8')
