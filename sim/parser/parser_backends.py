"""One parser contract for CLI providers; no driving or model tools are invoked."""
import argparse, json, os, shutil, subprocess, time, uuid, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).resolve().parent
SCHEMA = CONFIG.parent / 'engine/schema.json'
sys.path.insert(0, str(CONFIG.parent))
MODELS = json.loads((CONFIG / 'demo-models.json').read_text(encoding='utf-8-sig'))['models']

def executable(provider):
    configured = os.environ.get('ECE191_' + provider.upper(), provider)
    found = shutil.which(configured)
    if not found:
        raise RuntimeError(f'{provider} CLI is unavailable; configure its executable on PATH')
    return found

def validate(value, schema):
    # All providers receive the same schema; validate before map execution.
    from engine.contract import validate as validate_contract
    validate_contract(value, schema)

def parse(instruction, model_id, timeout=90):
    model=next(m for m in MODELS if m['id']==model_id)
    folder=(ROOT / os.environ.get('DEMO_TRACE_ROOT', 'logs'))/'parser'/str(uuid.uuid4())
    folder.mkdir(parents=True)
    schema=json.loads(SCHEMA.read_text(encoding='utf-8-sig'))
    prompt_path=ROOT / os.environ.get('ECE191_PARSER_PROMPT', str(CONFIG/'prompt.txt'))
    prompt=prompt_path.read_text(encoding='utf-8-sig')+'\nReturn only JSON matching this schema:\n'+json.dumps(schema)+'\nPASSENGER INPUT (JSON string):\n'+json.dumps(instruction,ensure_ascii=False)
    (folder/'request.json').write_text(json.dumps({'model':model,'instruction':instruction},ensure_ascii=False,indent=2),encoding='utf-8')
    env=os.environ.copy();env['PYTHONIOENCODING']='utf-8'
    if model['provider']=='codex':
        cmd=[executable('codex'),'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(folder),'-m',model['model'],'-c','model_reasoning_effort="low"','--output-schema',str(SCHEMA),'-o',str(folder/'parsed.json'),'--json','-']
    elif model['provider']=='claude':
        cmd=[executable('claude'),'-p','--safe-mode','--no-session-persistence','--tools','','--strict-mcp-config','--model',model['model'],'--effort','low','--output-format','json','--json-schema',json.dumps(schema)]
    elif model['provider']=='antigravity':
        cmd=[executable('agy'),'-p',prompt,'--model',model['model'],'--mode','plan','--disable-slash-commands','--output-format','json','--json-schema',str(SCHEMA),'--print-timeout','90s']
    else:
        # Fresh run directory, no project configuration; deny every tool.
        policy=folder/'deny-tools.toml'
        policy.write_text('[[rule]]\ntoolName = "*"\ndecision = "deny"\npriority = 999\n',encoding='utf-8')
        cmd=[executable('gemini'),'-m',model['model'],'-p','Parse the passenger input in stdin. No tools.','--output-format','json','--policy',str(policy)]
    start=time.perf_counter()
    try:
        proc=subprocess.run(cmd,input=prompt,cwd=folder,env=env,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'{model_id}: no complete response within {timeout}s; see {folder}') from None
    elapsed=time.perf_counter()-start
    (folder/'stdout.txt').write_text(proc.stdout,encoding='utf-8');(folder/'stderr.txt').write_text(proc.stderr,encoding='utf-8')
    if proc.returncode:
        try:failure=json.loads(proc.stdout)
        except (ValueError,TypeError):failure={}
        if failure.get('api_error_status')==429 or failure.get('api_error')=='usage_limit_reached':raise RuntimeError(f'{model_id}: provider usage limit reached; choose another configured model. No reset or spending-limit change was made. See {folder}')
        raise RuntimeError(f'{model_id}: CLI failed ({proc.returncode}); see {folder}')
    if model['provider']=='codex':
        value=json.loads((folder/'parsed.json').read_text(encoding='utf-8-sig'))
        metadata={}
    else:
        outer=json.loads(proc.stdout);metadata=outer.get('stats',outer.get('modelUsage',{}))
        if outer.get('is_error') or outer.get('error') or outer.get('status')=='ERROR':raise RuntimeError(f'{model_id}: provider error; see {folder}')
        value=outer.get('structured_output')
        if value is None:
            raw=outer.get('response',outer.get('result','')).strip()
            if raw.startswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0]
            value=json.loads(raw)
        (folder/'parsed.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    validate(value,schema)
    (folder/'raw-parsed.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    from semantic_contract_v21 import canonicalize
    value=canonicalize(instruction,value)
    validate(value,schema)
    (folder/'parsed.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    result={'model':model_id,'provider':model['provider'],'seconds':round(elapsed,3),'parsed':value,'run':str(folder),'provider_metadata':metadata}
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--model', required=True)
    cli.add_argument('--instruction', required=True)
    args = cli.parse_args()
    result = parse(args.instruction, args.model)
    result['parsed']['model_info'] = {'id': result['model'], 'parser_seconds': result['seconds']}
    print(json.dumps(result['parsed'], ensure_ascii=False))
