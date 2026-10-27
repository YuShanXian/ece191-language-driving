from pathlib import Path
root=Path('historical-project');p=root/'scripts/serve_v7_review.py';s=p.read_text()
s=s.replace('STATE=OUT/"reviews.json"','STATE=OUT/"reviews.json"\nfrom target_review_store import blank_targets,update_target\nTARGET_STATE=OUT/"targets.json"\nMAPS=json.loads((OUT/"target-maps.json").read_text())')
s=s.replace('  if url=="/api/state":','  if url=="/api/target-maps":self.reply(MAPS);return\n  if url=="/api/targets":self.reply(json.loads(TARGET_STATE.read_text()) if TARGET_STATE.exists() else blank_targets());return\n  if url=="/api/state":')
s=s.replace('  elif re.fullmatch(r"/plot/', '  elif url=="/target-picker.js":p=OUT/"target-picker.js"\n  elif re.fullmatch(r"/plot/')
s=s.replace(' def do_POST(self):\n', ''' def do_POST(self):
  if self.path=="/api/target":
   if self.headers.get("Origin") not in (None,"http://localhost:8770","http://127.0.0.1:8770") or self.headers.get("X-Review-App")!="v7-review":self.send_error(403);return
   try:
    n=int(self.headers.get("Content-Length","0"))
    if not 0<n<20000:raise ValueError()
    row=update_target(TARGET_STATE,json.loads(self.rfile.read(n)),MAPS)
    self.reply({"saved":True,"target":row})
   except (ValueError,KeyError,TypeError):self.reply({"error":"\u76ee\u6807\u9053\u8def\u6570\u636e\u65e0\u6548"},400)
   return
''')
(root/'scripts/serve_target_review.py').write_text(s,encoding='utf-8')
p=root/'runs/project-v3/instruction-priority-v7/human-review/index.html';s=p.read_text()
if '<script src="/target-picker.js"></script>' not in s:s=s.replace('</html>','<script src="/target-picker.js"></script></html>')
s=s.replace('\u672c\u8f6e\u4ece\u7a7a\u767d\u5f00\u59cb，\u65e7\u8bc4\u4ef7\u4fdd\u7559。','\u53ef\u4ee5\u5728\u5730\u56fe\u4e0a\u9009\u62e9\u76ee\u6807\u9053\u8def；\u5df2\u6709\u8bc4\u4ef7\u548c\u5907\u6ce8\u4fdd\u7559。')
p.write_text(s,encoding='utf-8')
print('Target endpoint and picker installed; review file untouched.')
