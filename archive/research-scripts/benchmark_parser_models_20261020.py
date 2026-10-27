import concurrent.futures,json,subprocess,time,statistics,random
from pathlib import Path
ROOT=Path(r'historical-project');out=ROOT/'runs/project-v3/model-selection-20261020';out.mkdir(exist_ok=True)
pwsh=r'local-user\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
models=['gpt-6-astra','gpt-6.1-sol','gpt-6-sol','gpt-6-luna','gpt-5.6-sol','gpt-5.6-terra','gpt-5.6-luna']
cases=[('distance','Drive 60 meters and stop.'),('sequence','\u5148\u53f3\u8f6c，\u7136\u540e\u8fdb\u5165\u4ece\u5de6\u6570\u7b2c\u4e8c\u6761\u8f66\u9053，\u518d\u5f0030\u7c73\u505c\u8f66。'),('speed_uturn','Make a U-turn, then drive at 18 km/h for 20 meters and stop.')]
def check(p,case):
 s=p.get('stages',[]);errors=[]
 if p.get('status')!='parsed' or p.get('unresolved_text'):errors.append('not parsed')
 expected={'distance':['go_straight'],'sequence':['turn_right','select_lane','go_straight'],'speed_uturn':['u_turn','go_straight']}[case]
 if [x.get('action') for x in s]!=expected:errors.append('action order')
 if s:
  last=s[-1];d={'distance':60,'sequence':30,'speed_uturn':20}[case]
  if last.get('travel_distance_m')!=d or last.get('stop_at_end') is not True:errors.append('distance/stop')
  if case=='speed_uturn' and abs((last.get('target_speed_mps') or 0)-5)>.01:errors.append('speed conversion')
  if any(x.get('trigger')!=('now' if i==0 else 'after_previous') for i,x in enumerate(s)):errors.append('trigger order')
  if case=='sequence' and (len(s)<2 or s[1].get('lane_reference')!='leftmost' or s[1].get('lane_number')!=2):errors.append('ordinal lane')
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
