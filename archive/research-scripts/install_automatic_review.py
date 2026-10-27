from pathlib import Path
root=Path('historical-project');out=root/'runs/project-v3/automatic-road-v9';tag='<script src="review.js"></script>'
for p in [out/'index.html',*out.glob('scene-??.html')]:
 s=p.read_text();
 if tag not in s:p.write_text(s+'\n'+tag,encoding='utf-8')
p=root/'scripts/report_automatic_roads_v9.py';s=p.read_text(encoding='utf-8-sig')
if '# Keep the manual review interface' not in s:
 s+='\n# Keep the manual review interface when regenerating plots.\nfor pagefile in [out/"index.html",*out.glob("scene-??.html")]:\n text=pagefile.read_text();tag=\'<script src="review.js"></script>\'\n if tag not in text:pagefile.write_text(text+"\\n"+tag,encoding="utf-8")\n'
 p.write_text(s,encoding='utf-8')
