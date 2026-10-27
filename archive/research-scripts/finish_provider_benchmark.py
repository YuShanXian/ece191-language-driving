"""Wait for the first serial sweep, then test Gemini and repeat shortlisted models."""
import ctypes,subprocess,sys,json
from pathlib import Path
from benchmark_providers import OUT,summarize
from parser_backends import MODELS,ROOT
kernel=ctypes.windll.kernel32
kernel.OpenProcess.restype=ctypes.c_void_p
kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
kernel.CloseHandle.argtypes=[ctypes.c_void_p]
handle=kernel.OpenProcess(0x100000,False,int(sys.argv[1]))
if handle:
 kernel.WaitForSingleObject(handle,0xFFFFFFFF);kernel.CloseHandle(handle)
script=str(ROOT/'scripts/benchmark_providers.py')
subprocess.run([sys.executable,script,'--models','gemini-3.8-flash-low'],check=True)
results=json.loads((OUT/'results.json').read_text(encoding='utf-8'))
rows=summarize(results)
eligible=[r for r in rows if r['total']>=16 and r['passed']==r['total']]
eligible.sort(key=lambda r:r['median'])
shortlist=[r['model'] for r in eligible[:4]]
if shortlist:
 subprocess.run([sys.executable,script,'--models',*shortlist,'--repeat','2'],check=True)
results=json.loads((OUT/'results.json').read_text(encoding='utf-8'));rows=summarize(results)
eligible=[r for r in rows if r['model'] in shortlist and r['passed']==r['total'] and r['total']>=32]
eligible.sort(key=lambda r:(r['median'],r['p90']))
selected=[r['model'] for r in eligible[:4]]
default=selected[0] if selected else 'gpt-5.6-luna'
if not selected:selected=[default]
labels={'gpt-5.6-luna':'GPT-5.6 Luna · Low','gpt-6-luna':'GPT-6 Luna · Low','claude-haiku-5-5':'Claude Haiku 5.5 · Low','claude-sonnet-5-5':'Claude Sonnet 5.5 · Low','claude-opus-5-5':'Claude Opus 5.5 · Low'}
catalog={'default':default,'models':[dict(m,label=labels.get(m['id'],m['label']),enabled=m['id'] in selected) for m in MODELS]}
(ROOT/'config/language-parser-v4/demo-models.json').write_text(json.dumps(catalog,indent=2),encoding='utf-8')
decision={'default':default,'menu':selected,'rule':'All 16 cases must pass twice, then lowest median elapsed CLI time; 32 trials is only a screening sample.','flash_lite':'Unavailable through the signed-in Google CLI; Gemini 3.8 Flash Low tested separately.','results':rows}
(OUT/'decision.json').write_text(json.dumps(decision,indent=2),encoding='utf-8')
print(json.dumps(decision,indent=2),flush=True)
