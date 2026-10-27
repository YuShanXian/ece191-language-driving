import concurrent.futures,json,subprocess,time,statistics,random
from pathlib import Path
ROOT=Path(r'historical-project');out=ROOT/'runs/project-v3/model-selection-20261020/luna-followup';out.mkdir(exist_ok=True)
pwsh=r'local-user\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
models=['gpt-6-luna','gpt-5.6-luna']
cases=[('mph','Set the speed to 15 mph.'),('units','Drive 0.05 kilometers and stop.'),('negation','Do not turn left.'),('ambiguity','Left.'),('condition','Wait for the light to turn green, then turn right.'),('sequence2','\u5148\u5411\u53f3\u6362\u4e00\u6761\u8f66\u9053，\u518d\u6389\u5934，\u7136\u540e\u5f0010\u7c73\u505c\u8f66。')]
def check(p,case):
 s=p.get('stages',[]);errors=[];actions=[x.get('action') for x in s]
 if case in ('negation','ambiguity'):
  if p.get('status')!='needs_clarification':errors.append('should clarify without positive action')
  return errors
 if p.get('status')!='parsed':errors.append('not parsed')
 if case=='mph' and (actions!=['set_speed'] or abs((s[0].get('target_speed_mps') or 0)-6.7056)>.01):errors.append('mph conversion')
 if case=='units' and (actions!=['go_straight'] or s[0].get('travel_distance_m')!=50 or not s[0].get('stop_at_end')):errors.append('km distance conversion')
 if case=='condition':
  if 'turn_right' not in actions or not any(x.get('trigger') not in ('now','after_previous') or x.get('constraints') for x in s):errors.append('lost green light condition')
 if case=='sequence2':
  if actions!=['lane_change_right','u_turn','go_straight']:errors.append('action order')
  if not s or s[-1].get('travel_distance_m')!=10 or not s[-1].get('stop_at_end'):errors.append('distance/stop')
 return errors
results=[]
def run(job):
 model,case,text=job;t=time.perf_counter()
 try:
  proc=subprocess.run([pwsh,'-NoProfile','-File',str(ROOT/'scripts/parse_navigation_llm_v4.ps1'),'-Model',model,'-Reasoning','low','-Instruction',text],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
  elapsed=time.perf_counter()-t
  import re
  match=re.search(r'Saved run: (.+)',proc.stdout)
  if not match:raise ValueError(proc.stderr[-700:] or proc.stdout[-700:])
  folder=Path(match[1].strip());p=json.loads((folder/'parsed.json').read_text(encoding='utf-8-sig'));errors=check(p,case)
  result={'model':model,'case':case,'seconds':round(elapsed,3),'passed':not errors,'errors':errors,'run':str(folder),'parsed':p}
 except Exception as e:result={'model':model,'case':case,'seconds':round(time.perf_counter()-t,3),'passed':False,'errors':[str(e)]}
 return result
# Each round tests the same instruction across all models, with at most 3 concurrent requests.
for case,text in cases:
 jobs=[(m,case,text) for m in models];random.Random(case).shuffle(jobs)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for r in pool.map(run,jobs):
   results.append(r);(out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k not in ('parsed','run')},ensure_ascii=False),flush=True)
summary=[]
for m in models:
 rs=[r for r in results if r['model']==m];summary.append({'model':m,'passed':sum(r['passed'] for r in rs),'total':len(rs),'median_seconds':round(statistics.median(r['seconds'] for r in rs),2),'times':[r['seconds'] for r in rs]})
summary.sort(key=lambda r:r['median_seconds']);(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2),flush=True)
