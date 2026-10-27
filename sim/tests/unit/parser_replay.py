"""Replay previously recorded provider responses; does not invoke an LLM."""
import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'sim/parser'))
sys.path.insert(0,str(Path(__file__).parent))
sys.path.insert(0,str(Path(__file__).parents[2]))
from semantic_contract_v21 import canonicalize
from language_corpus import CASES,grade
from engine.normalize import normalize
from engine.contract import validate,validate_stage
cases={c['id']:c for c in CASES};records={};failures=[];changed=0
for line in (Path(__file__).parents[1]/'results/historical-language/language-results.jsonl').read_text(encoding='utf-8').splitlines():
    r=json.loads(line)
    if 'parsed' in r:records[r['id']]=r
for key,r in records.items():
    try:
        canonical=canonicalize(r['text'],r['parsed']);validate(canonical)
        errors=grade(canonical,cases[key])
        normalized=normalize(canonical)
        for st in normalized['stages']:validate_stage(st)
        if normalized!=canonical:changed+=1
        if errors:failures.append({'id':key,'text':r['text'],'errors':errors})
    except Exception as error:failures.append({'id':key,'text':r['text'],'error':str(error)})
result={'kind':'Offline replay of previously recorded real model responses; no new LLM calls','total_cases':len(cases),'replayed':len(records),'normalized':changed,'passed':len(records)-len(failures),'failures':failures}
(Path(__file__).parents[1]/'results/parser-replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False));sys.exit(bool(failures))
