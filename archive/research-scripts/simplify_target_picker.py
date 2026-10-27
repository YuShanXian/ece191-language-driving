from pathlib import Path
import json
root=Path('historical-project');out=root/'runs/project-v3/instruction-priority-v7/human-review';p=out/'target-picker.js';s=p.read_text(encoding='utf-8-sig')
a=s.index(' el.onclick=e=>');b=s.index(" document.getElementById('target-mode-",a)
s=s[:a]+''' el.onclick=e=>{const pt=el.createSVGPoint();pt.x=e.clientX;pt.y=e.clientY;const matrix=el.getScreenCTM();const q=pt.matrixTransform(matrix.inverse());const nearest=nearestRoads(s,q.x,-q.y,9/Math.hypot(matrix.a,matrix.b))[0];if(!nearest)return;toggleAlternative(row,nearest.road.id);saveTarget(s,c);drawTarget(s,c)};
 const desc=[...row.road_ids].sort().map(k=>map.roads.find(r=>r.id===k)?.label||k).join('、');
 document.getElementById('target-selected-'+id).textContent=row.mode==='roads'?'\u5df2\u9009 '+row.road_ids.length+' \u6761\u53ef\u884c\u5907\u9009：'+desc:({unselected:'\u70b9\u51fb\u9053\u8def\u9009\u62e9\u53ef\u884c\u5907\u9009',none:'\u8fd9\u91cc\u4e0d\u80fd\u6267\u884c\u8be5\u52a8\u4f5c',continue:'\u6cbf\u9053\u8def\u7ee7\u7eed\u884c\u9a76',uncertain:'\u6682\u65f6\u65e0\u6cd5\u5224\u65ad'})[row.mode];
'''+s[b:]
s=s.replace('const targetView={},targetNearby={},targetPreview={},targetRevision={};','const targetView={},targetPreview={},targetRevision={};')
s=s.replace('function segDistance(','''function toggleAlternative(row,key){row.road_ids=row.road_ids.includes(key)?row.road_ids.filter(k=>k!==key):[...row.road_ids,key];row.road_ids.sort();row.mode=row.road_ids.length?'roads':'unselected';row.selection_semantics='feasible_alternatives';}
function segDistance(''')
s=s.replace('\u4f60\u5e0c\u671b\u8f66\u8f86\u8d70\u54ea\u6761\u9053\u8def？','\u54ea\u4e9b\u9053\u8def\u90fd\u53ef\u4ee5\u8d70？').replace('\u7070\u7ebf＝\u5730\u56fe\u9053\u8def\u4e2d\u5fc3\u7ebf；\u84dd\u8272\u865a\u7ebf＝\u7a0b\u5e8f\u5f53\u524d\u8def\u7ebf；\u7c89\u8272＝\u4f60\u9009\u62e9\u7684\u9053\u8def。\u53ef\u6309\u987a\u5e8f\u9009\u591a\u6bb5，\u4f8b\u5982“\u5148\u53f3\u4fa7\u8f66\u9053，\u518d\u53f3\u8f6c\u51fa\u53e3”。\u9009\u76ee\u6807\u4e0d\u4f1a\u81ea\u52a8\u6539\u4f60\u7684\u6210\u529f／\u5931\u8d25\u5224\u65ad。','\u70b9\u4e00\u4e0b\u9009\u4e2d，\u518d\u70b9\u53d6\u6d88。\u6bcf\u6761\u7c89\u8272\u9053\u8def\u90fd\u662f\u4f60\u8ba4\u53ef\u7684\u53ef\u884c\u5907\u9009，\u6ca1\u6709\u5148\u540e\u987a\u5e8f。\u84dd\u8272\u865a\u7ebf\u662f\u7a0b\u5e8f\u5f53\u524d\u8def\u7ebf。')
s=s.replace('<div id="target-near-\'+id+\'" style="min-height:65px"></div>','')
s=s.replace('<button data-edit="undo">\u64a4\u9500\u6700\u540e\u4e00\u6bb5</button> ','').replace("if(b.dataset.edit==='undo')row.road_ids.pop();",'')
s=s.replace('\u4f7f\u7528\u6211\u70b9\u51fb\u7684\u9053\u8def','\u6240\u9009\u9053\u8def\u5747\u53ef\u884c').replace('\u6e05\u9664\u76ee\u6807\u9009\u62e9','\u6e05\u7a7a\u9009\u62e9').replace('\u76ee\u6807\u5c1a\u672a\u586b\u5199','\u5c1a\u672a\u9009\u62e9').replace('\u5df2\u8bfb\u53d6\u4fdd\u5b58\u7684\u76ee\u6807','\u5df2\u8bfb\u53d6\u4fdd\u5b58\u7684\u5907\u9009')
p.write_text(s,encoding='utf-8')
p=root/'scripts/target_review_store.py';s=p.read_text();s=s.replace("'schema':1", "'schema':2,'selection_semantics':'feasible_alternatives'").replace("'road sequence'","'road alternatives'")
s=s.replace("'road_ids':ids,'updated_at'","'road_ids':sorted(ids),'selection_semantics':'feasible_alternatives','updated_at'")
s=s.replace("index=(validated['scene']-1)*5+validated['command'];data['reviews'][index]=validated", "data['schema']=2;data['selection_semantics']='feasible_alternatives'\n  index=(validated['scene']-1)*5+validated['command'];data['reviews'][index]=validated")
p.write_text(s,encoding='utf-8')
p=out/'targets.json'
if p.exists():
 data=json.loads(p.read_text());data['schema']=2;data['selection_semantics']='feasible_alternatives'
 for r in data['reviews']:r['selection_semantics']='feasible_alternatives';r['road_ids']=sorted(r['road_ids'])
 p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('One-click unordered alternatives installed; existing road IDs and verdicts preserved.')
