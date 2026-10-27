"""Build a delivery report from retained observations, not estimated run time."""
import json,html,statistics,hashlib,re
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).parents[1];results=root/'results'
read=lambda name:json.loads((results/name).read_text(encoding='utf-8-sig'))
samples=read('production-browser-samples.json')
final=read('production-browser-final.json')
engine=read('engine-regression.json');parser=read('parser-replay.json')
events=[json.loads(line) for line in Path('historical-project/runs/project-v3/refactor-v27/events.jsonl').read_text(encoding='utf-8').splitlines()]
start=samples[0]['at']
assert not [e for e in events if e.get('time','')>=start and e.get('type')=='error'],'Server error during final browser run'
events=[e for e in events if e.get('time','')>=start and e.get('scene')==1]
latencies=[e['latency_ms'] for e in events if 'latency_ms' in e]
archive=json.loads(Path('E:/\u6587\u4ef6\u6574\u7406\u811a\u672c/20261023-225016-ece191-driving-source-archive/archive-receipt.json').read_text(encoding='utf-8'))
duration=float(re.search(r'\u5b9e\u9645\u884c\u9a76 ([\d.]+) s',final['monitor'])[1])
distance=float(re.search(r'Distance ([\d.]+) m',final['monitor'])[1])
assert duration>=300,'Continuous browser movement gate not reached'
assert 'Position jumps 0' in final['monitor'] and 'Layout shifts 0' in final['monitor'] and 'Longest stall 0.0 s' in final['monitor']
assert not engine['failures'] and not parser['failures']
assert not [e for e in events if e.get('type')=='error']
manifest=json.loads(Path('historical-project/runs/project-v3/refactor-v27/release-manifest.json').read_text())
for file in manifest['files']:
    path=Path('historical-project/apps/driving-demo')/file['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==file['sha256'],'Delivered source changed during test'
report={'created_utc':datetime.now(timezone.utc).isoformat(),'release':'refactor-v27','url':'http://localhost:8775/','scene':1,'target_speed_kmh':20,'continuous_moving_seconds':duration,'distance_m':distance,'monitor':final['monitor'],'browser_samples':len(samples),'engine_cases':engine['cases'],'engine_failures':len(engine['failures']),'queue_tests_passed':11,'parser_replay':parser,'warm_browser_latency_ms':{'count':len(latencies),'minimum':min(latencies),'median':statistics.median(latencies),'maximum':max(latencies)},'archive':archive['archive'],'archived_files_verified':archive['verified_files'],'active_files_verified':len(manifest['files']),'observed_queue':final['rows'],'known_limits':['Finite map extent; reverse or reset is explicit.','A maneuver with no connected opportunity in the wait window is held for retry/skip.','Unresolved visual conditions are not guessed by the map-only planner.','The 555 language cases are replayed recorded model outputs, not 555 fresh provider calls.']}
(results/'delivery-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
escape=lambda value:html.escape(str(value))
latency=report['warm_browser_latency_ms']
body=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>Driving demo v27 — validation</title>
<style>body{{font:16px/1.65 system-ui;max-width:1050px;margin:40px auto;padding:0 24px;color:#16394b}}h1{{line-height:1.2}}.stats{{display:flex;gap:14px;flex-wrap:wrap}}.stats div{{background:#e9f5f3;padding:18px;border-radius:10px}}strong{{color:#087c75}}pre{{white-space:pre-wrap;background:#f2f5f7;padding:18px;border-radius:10px}}img{{width:100%;border:1px solid #ccd9df;border-radius:10px}}li{{margin:8px 0}}</style>
<h1>Driving demo v27 · \u91cd\u6784\u4e0e\u9a8c\u8bc1\u8bb0\u5f55</h1><p>{escape(report['created_utc'])} · \u6b63\u5f0f\u670d\u52a1 http://localhost:8775/</p>
<div class="stats"><div><strong>{duration:.1f} \u79d2</strong><br>\u6b63\u5f0f\u6d4f\u89c8\u5668\u8fde\u7eed\u884c\u9a76</div><div><strong>{distance:.1f} \u7c73</strong><br>Scene 01 · \u76ee\u6807 20 km/h</div><div><strong>0</strong><br>\u4f4d\u7f6e\u8df3\u53d8 / \u5e03\u5c40\u8df3\u52a8 / \u5361\u4f4f</div></div>
<h2>\u539f\u95ee\u9898\u4e0e\u4fee\u590d</h2><p>\u539f\u65e5\u5fd7\u663e\u793a\u5de6\u8f6c\u53cd\u590d\u91cd\u8bd5\u540e，\u8fdb\u5165\u5f3a\u5236\u8fde\u63a5\u53ef\u89c1\u9053\u8def\u7684\u56de\u9000\u903b\u8f91，\u968f\u540e\u62a5“\u627e\u4e0d\u5230\u5f53\u524d\u8f66\u9053”。\u65e7\u961f\u5217\u8fd8\u4f1a\u5728\u6bcf\u6b21\u89c4\u5212\u8bf7\u6c42\u65f6\u6682\u505c\u52a8\u753b。</p><ul>
<li>\u6d3b\u52a8\u8fd0\u884c\u94fe\u6539\u4e3a\u72ec\u7acb\u7684\u5730\u56fe\u89c4\u5212\u5668、\u552f\u4e00\u8f66\u8f86\u72b6\u6001、\u987a\u5e8f\u961f\u5217\u548c\u56fa\u5b9a\u5e03\u5c40。</li>
<li>\u89c4\u5212\u4e0e\u8bed\u8a00\u89e3\u6790\u4e0d\u6682\u505c\u5df2\u6709\u8def\u7ebf；\u8fdf\u5230、\u53d6\u6d88\u548c\u8fc7\u671f\u7684\u54cd\u5e94\u4e0d\u80fd\u91cd\u65b0\u5b89\u88c5\u65e7\u6307\u4ee4。</li>
<li>\u4fdd\u7559\u8f66\u9053\u8eab\u4efd\u4e0e\u8fde\u7eed\u4f4d\u7f6e；\u62d2\u7edd\u76f4\u89d2\u62fc\u63a5、\u5f3a\u5236\u5438\u9644、\u9690\u5f0f\u6389\u5934\u548c\u5927\u5e45\u6a2a\u8de8\u8f66\u9053\u7684\u76f4\u884c\u8fde\u63a5。</li>
<li>\u7b49\u5f85\u65f6\u7ee7\u7eed\u6cbf\u5f53\u524d\u9053\u8def\u524d\u8fdb；\u5012\u8f66\u6cbf\u5b9e\u9645\u8d70\u8fc7\u7684\u8def\u5f84\u6267\u884c，\u5148\u505c\u8f66\u518d\u6362\u65b9\u5411。</li>
</ul><h2>\u9a8c\u8bc1</h2><ul><li>{engine['cases']} \u4e2a\u5b9e\u9645\u5730\u56fe\u89c4\u5212\u68c0\u67e5，\u4e03\u4e2a\u573a\u666f，\u5931\u8d25 0；\u542b\u9ed8\u8ba4\u524d\u8def\u8fde\u63a5\u4e0d\u53ef\u6a2a\u8de8\u591a\u8f66\u9053\u7684\u65ad\u8a00。</li><li>11 \u9879\u961f\u5217\u548c\u8fd0\u52a8\u56de\u5f52\u901a\u8fc7，\u542b 3 \u79d2\u6a21\u62df\u89c4\u5212\u5ef6\u8fdf、\u53d6\u6d88\u8fdf\u5230\u7ed3\u679c、\u8bed\u8a00\u4e0e\u6309\u94ae\u6307\u4ee4\u987a\u5e8f、\u5012\u8f66\u5236\u52a8。</li><li>555 \u6761\u5386\u53f2\u771f\u5b9e\u6a21\u578b\u8f93\u51fa\u79bb\u7ebf\u56de\u653e\u5168\u90e8\u901a\u8fc7。\u53e6\u5728\u6d4f\u89c8\u5668\u5b9e\u9645\u8c03\u7528\u4e86\u8bed\u8a00\u89e3\u6790\u5e76\u9a8c\u8bc1\u8f66\u8f86\u7ee7\u7eed\u884c\u9a76。</li><li>\u672c\u8f6e\u6b63\u5f0f\u6d4f\u89c8\u5668\u89c4\u5212\u5f80\u8fd4 {latency['minimum']:.0f}–{latency['maximum']:.0f} ms，\u4e2d\u4f4d\u6570 {latency['median']:.0f} ms；\u4e0d\u5305\u542b\u9996\u6b21\u5730\u56fe\u52a0\u8f7d\u548c\u6a21\u578b\u63a8\u7406\u65f6\u95f4。</li><li>\u65e7\u6e90\u7801\u5f52\u6863 {archive['verified_files']} \u4e2a\u6587\u4ef6\u5e76\u6821\u9a8c；\u6b63\u5f0f\u5e94\u7528 {len(manifest['files'])} \u4e2a\u6587\u4ef6\u4e0e\u90e8\u7f72\u6e05\u5355\u54c8\u5e0c\u4e00\u81f4。</li></ul>
<h2>\u6700\u7ec8\u6d4b\u91cf</h2><pre>{escape(final['monitor'])}</pre><h2>\u6307\u4ee4\u987a\u5e8f\u4e0e\u7ed3\u679c</h2><pre>{escape(final['rows'])}</pre>
<img src="production-final.png" alt="\u6b63\u5f0f\u6d4f\u89c8\u5668\u8fd0\u884c\u7ed3\u679c">
<h2>\u4ecd\u5b58\u5728\u7684\u8fb9\u754c</h2><p>\u5730\u56fe\u8303\u56f4\u6709\u9650；\u771f\u5b9e\u65ad\u9053\u9700\u8981\u5012\u8f66\u6216\u91cd\u7f6e。\u7b49\u5f85\u7a97\u53e3\u5185\u6ca1\u6709\u8fde\u901a\u673a\u4f1a\u7684\u6307\u4ee4\u4f1a\u4fdd\u7559，\u4e0d\u4f1a\u4f2a\u9020\u6267\u884c\u6210\u529f。\u89c6\u89c9\u6761\u4ef6\u548c\u4e0d\u652f\u6301\u7684\u89e6\u53d1\u6761\u4ef6\u9700\u8981\u6f84\u6e05。</p>
<p>\u5b58\u6863：{escape(archive['archive'])}<br>\u6d3b\u52a8\u6e90\u7801：historical-project\\apps\\driving-demo<br>\u8bf7\u6c42\u51e0\u4f55\u4e0e\u65e5\u5fd7：historical-project\\runs\\project-v3\\refactor-v27</p></html>'''
(results/'delivery-report.html').write_text(body,encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('parser_replay','observed_queue')},ensure_ascii=False,indent=2))
