"""Persistent instruction + measured progress + per-checkpoint MTR proposals."""
import argparse,json,re
from mtr_project.paths import ROOT,write_json,sha256
from mtr_project.planner import OfflinePlanner
from mtr_project.stages import Observation


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default='annotation-sequence-v1')
    parser.add_argument('--replay',default='doplan_006160-window-v2-corridor-v1')
    parser.add_argument('--variant',default='baseline',help='baseline or simple project-v2 experiment directory name');args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.variant):raise ValueError('Simple variant name required')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.tag):raise ValueError('Simple tag required')
    folder=ROOT/'runs/project-v2'/args.tag
    manifest=json.loads((folder/'sequence-manifest.json').read_text())
    spec=json.loads((folder/'sequence-config.json').read_text())
    if len(manifest)!=len(spec['frames']):raise ValueError('Sequence incomplete')
    if args.variant!='baseline':
        manifest=[{**r,'source_key':r['key'],'key':args.variant+'--'+r['key'],
                   'run':'project-v2/'+args.variant+'/'+r['key'],
                   'screen_sha256':sha256(ROOT/'runs/project-v2'/args.variant/r['key']/'anchored_feasibility.json')} for r in manifest]
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.replay):raise ValueError('Simple replay name required')
    trace_path=ROOT/'runs/project-v2/replay'/f'{args.replay}.json'
    replay=json.loads(trace_path.read_text());planner=OfflinePlanner(spec['instruction'])
    if replay['instruction']!=spec['instruction'] or any(r['clip']!=replay['source_clip'] for r in manifest):raise ValueError('Replay and candidate sequence refer to different instructions or recordings')
    lookup={r['timestamp_us']:r for r in manifest};observations=[];checkpoints=[]
    for measured in replay['trace']:
        timestamp=measured['timestamp_us'];scene=lookup.get(timestamp);candidates=[]
        if scene:
            path=ROOT/'runs'/scene['run']/'anchored_feasibility.json'
            if sha256(path)!=scene['screen_sha256']:raise ValueError('Cached screen changed')
            candidates=json.loads(path.read_text())['candidates']
        observation=Observation(timestamp/1e6,*measured['xy'],measured['speed_mps'],
                                completed_actions=tuple(measured['observed_actions']))
        result=planner.step(observation,candidates)
        observations.append({'timestamp_us':timestamp,'stage':result.get('stage'),'observed_actions':measured['observed_actions']})
        if scene:
            checkpoints.append({**scene,'speed_mps':measured['speed_mps'],'passing_candidates':sum(c['passes_current_checks'] for c in candidates),
                                'selection':result})
    if len(checkpoints)!=len(manifest):raise ValueError('An exact checkpoint is missing from the causal observation trace')
    report={'instruction':spec['instruction'],'variant':args.variant,'checkpoints':checkpoints,'observations':observations,
            'final_stage':planner.machine.snapshot(),'source_sha256':{'manifest':sha256(folder/'sequence-manifest.json'),
                'observations':sha256(trace_path),'configuration':sha256(folder/'sequence-config.json'),
                'planner':sha256(ROOT/'scripts/mtr_project/planner.py'),'evaluator':sha256(__file__),
                **{p:sha256(ROOT/'scripts'/p) for p in ['mtr_project/stages.py','mtr_project/language.py','language_selector.py']}},
            'command_issue_time_known':False,'activation_convention':'First annotation frame, for demonstration only.',
            'scope':'Offline recorded-state replay. The connector observer is experimental; proposals are never executed. Checkpoints selected after inspecting this clip, so this is not semantic accuracy or closed-loop success.'}
    if args.variant!='baseline':report['scope']+=' Experimental candidate pool: consult each candidate report for connector geometry and any trajectory adjustment. Lane-marking legality is not established.'
    name='sequence-report.json' if args.variant=='baseline' else 'sequence-report-'+args.variant+'.json'
    write_json(folder/name,report)
    print(json.dumps([{k:r[k] for k in ['video_frame','gps_elapsed_seconds','passing_candidates']}|
                      {k:r['selection'][k] for k in ['status','candidate']} for r in checkpoints],indent=2))


if __name__=='__main__':main()
