import json,sys,time,hashlib,concurrent.futures
from pathlib import Path
r=Path('historical-project');sys.path.insert(0,str(r/'scripts'));from parser_backends import parse
out=r/'runs/project-v3/command-audit-v17';inputs=json.loads((out/'unique-inputs.json').read_text(encoding='utf-8'));dest=out/'fresh-parses';dest.mkdir(exist_ok=True)
def work(text):
 key=hashlib.sha256(text.encode()).hexdigest()[:16];p=dest/(key+'.json')
 if p.exists():return json.loads(p.read_text(encoding='utf-8'))
 try:
  x=parse(text,'claude-sonnet-5-5');row={'instruction':text,'parsed':x['parsed'],'seconds':x['seconds'],'run':x['run']}
 except Exception as e:row={'instruction':text,'error':str(e)}
 p.write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8');return row
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for f in concurrent.futures.as_completed([pool.submit(work,t) for t in inputs]):
  row=f.result();rows.append(row);(out/'fresh-parse-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'done':len(rows),'total':len(inputs),'input':row['instruction'],'status':row.get('parsed',{}).get('status',row.get('error'))},ensure_ascii=False),flush=True)
