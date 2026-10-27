from pathlib import Path
root=Path('historical-project');out=root/'runs/project-v3/automatic-road-v9'
p=root/'scripts/serve_automatic_road_report.py';s=p.read_text(encoding='utf-8-sig');s=s.replace('from automatic_review_store import read_reviews,save_review','from automatic_review_store import read_reviews,save_review\nfrom mtr_candidate_review_store import save_candidates');s=s.replace("  if name=='api/reviews':", "  if name=='api/candidate-reviews':self.reply(read_reviews(BASE/'human-review/candidate-selections.json'));return\n  if name=='api/candidate-data':self.reply(json.loads((BASE/'candidate-picker-data.json').read_text()));return\n  if name=='api/reviews':");s=s.replace("('index.html','review.js')","('index.html','review.js','candidate-picker.js')");s=s.replace("if self.path!='/api/review':","if self.path not in ('/api/review','/api/candidate-review'):");s=s.replace("row=save_review(REVIEWS,value)","row=save_candidates(BASE/'human-review/candidate-selections.json',value) if self.path=='/api/candidate-review' else save_review(REVIEWS,value)");p.write_text(s,encoding='utf-8')
tag='<script src="candidate-picker.js"></script>'
for p in out.glob('scene-??.html'):
 s=p.read_text();
 if tag not in s:p.write_text(s+'\n'+tag,encoding='utf-8')
p=root/'scripts/report_automatic_roads_v9.py';s=p.read_text(encoding='utf-8-sig')
s+='\n# Preserve independent manual MTR-candidate selection panels.\nfor pagefile in out.glob("scene-??.html"):\n text=pagefile.read_text();tag=\'<script src="candidate-picker.js"></script>\'\n if tag not in text:pagefile.write_text(text+"\\n"+tag,encoding="utf-8")\n';p.write_text(s,encoding='utf-8')
