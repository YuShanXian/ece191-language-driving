"""Versioned, resumable convert -> MTR -> checks pipeline. No model training."""
import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from mtr_project.paths import ROOT, sha256, write_json
from mtr_project.manifests import read_manifest,retain_completed_window

def output_hashes(outputs):
    paths=set(Path(p) for p in outputs)
    for path in list(paths):
        if path.name=='conversion.json' and path.is_file():
            conversion=json.loads(path.read_text());scenario=conversion.get('scenario')
            if scenario:
                child=(path.parent/scenario).resolve()
                if not child.is_relative_to(path.parent.resolve()):raise ValueError('Scenario path escapes converted input directory')
                paths.update([child,path.parent/'dataset_mapping.pkl',path.parent/'dataset_summary.pkl'])
    return {str(p):sha256(p) for p in sorted(paths)}

def stage(name, command, logdir, inputs, outputs, *, allow_new=True):
    receipt=logdir/f'{name}.json'
    fingerprint=hashlib.sha256(json.dumps({'command':command,'inputs':inputs},sort_keys=True).encode()).hexdigest()
    if receipt.exists():
        previous=json.loads(receipt.read_text())
        if previous.get('fingerprint')==fingerprint and previous.get('returncode')==0 and all(Path(p).exists() for p in outputs):
            if 'output_sha256' in previous:
                if output_hashes(outputs)!=previous['output_sha256']:raise RuntimeError(f'Cached outputs changed; preserve receipt and investigate: {receipt}')
                print('CACHED (content verified)',logdir.name,name,flush=True)
            else:print('CACHED (legacy receipt; original output hashes unavailable)',logdir.name,name,flush=True)
            return
        raise RuntimeError(f'Stage differs from receipt; use a new --tag, never overwrite results: {receipt}')
    if not allow_new:raise RuntimeError(f'No reusable receipt for {name}; cached-only mode cannot start computation: {receipt}')
    logdir.mkdir(parents=True,exist_ok=True)
    started=time.time()
    print('START',logdir.name,name,flush=True)
    with (logdir/f'{name}.log').open('w') as stream:
        result=subprocess.run([sys.executable,*command],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    hashes={};validation_error=None
    if result.returncode==0:
        try:hashes=output_hashes(outputs)
        except (OSError,ValueError) as exc:validation_error=str(exc)
    write_json(receipt,{'command':command,'fingerprint':fingerprint,'inputs':inputs,
                        'returncode':result.returncode,'elapsed_sec':time.time()-started,
                        'outputs':[str(p) for p in outputs],'output_sha256':hashes,'output_validation_error':validation_error})
    if result.returncode:
        print((logdir/f'{name}.log').read_text()[-5000:],flush=True)
        raise RuntimeError(f'{name} failed; see {logdir}')
    if validation_error:raise RuntimeError(f'Output validation failed for {name}: {validation_error}')
    print('DONE',logdir.name,name,round(time.time()-started,1),'seconds',flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split',choices=['development','evaluation'],default='development')
    parser.add_argument('--tag',default='baseline-v1')
    parser.add_argument('--fractions',type=float,nargs='+',default=[.2,.5,.8])
    parser.add_argument('--limit',type=int)
    parser.add_argument('--cached-only',action='store_true',help='Refuse to start any missing conversion, inference or screening stage')
    args=parser.parse_args()
    if not args.tag.replace('-','').replace('_','').isalnum():parser.error('Simple tag required')
    if not args.fractions or any(not 0<f<1 for f in args.fractions):parser.error('Fractions must be inside (0,1)')
    if len(set(args.fractions))!=len(args.fractions):parser.error('Duplicate fractions')
    if args.limit is not None and args.limit<1:parser.error('Limit must be positive')
    if len({round(f*1000) for f in args.fractions})!=len(args.fractions):parser.error('Fractions collide in window identifiers; use distinct millifractions')
    config=json.loads((ROOT/'config/project-v2-scenes.json').read_text())
    selected=[r for r in config['selected'] if r['split']==args.split]
    expected=[f'{args.split}-{i:02d}-f{round(f*1000):03d}' for i in range(len(selected)) for f in args.fractions]
    manifest=ROOT/'runs/project-v2'/args.tag/f'{args.split}-manifest.json'
    read_manifest(manifest,expected)
    checkpoint=ROOT/'weights/pretrained_weights/checkpoint_for_val_test.ckpt'
    checkpoint_hash=sha256(checkpoint)
    map_hash=sha256(ROOT/'data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg')
    records=[]
    for index,item in enumerate(selected):
        db=ROOT/'data/nuplan/db'/f"{item['clip']}.db"
        if not db.exists():raise FileNotFoundError(f'Finish fetch_project_scenes.py first: {db}')
        db_hash=sha256(db)
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
            start,end=conn.execute('SELECT MIN(timestamp), MAX(timestamp) FROM lidar_pc').fetchone()
        for fraction in args.fractions:
            if args.limit is not None and len(records)>=args.limit:break
            seconds=round((end-start)/1e6*fraction,3)
            key=f"{args.split}-{index:02d}-f{round(fraction*1000):03d}"
            sample=f'project-v2/{args.tag}/{key}'
            run=f'project-v2/{args.tag}/{key}'
            sample_dir=ROOT/'samples'/sample;run_dir=ROOT/'runs'/run
            logdir=ROOT/'runs/project-v2'/args.tag/'execution'/key
            inputs={'db_sha256':db_hash,'converter_sha256':sha256(ROOT/'scripts/convert_nuplan_mtr.py'),
                    'map_sha256':map_hash}
            stage('convert',['scripts/convert_nuplan_mtr.py','--db',str(db),'--seconds',str(seconds),'--output',str(sample_dir)],logdir,inputs,[sample_dir/'conversion.json'],allow_new=not args.cached_only)
            stage('infer',['scripts/export_mtr_candidates.py','--checkpoint',str(checkpoint),'--data',str(sample_dir),
                           '--output',str(run_dir),'--ego-only'],logdir,
                  {'conversion':sha256(sample_dir/'conversion.json'),'checkpoint':checkpoint_hash,
                   'smoke_script':sha256(ROOT/'scripts/smoke_mtr.py'),'export_script':sha256(ROOT/'scripts/export_mtr_candidates.py')},[run_dir/'internal_0000.npz'],allow_new=not args.cached_only)
            stage('check',['scripts/screen_project_scene.py','--sample',sample,'--run',run],logdir,
                  {'candidates':sha256(run_dir/'internal_0000.npz'),
                   'sources':{p:sha256(ROOT/'scripts'/p) for p in ['screen_project_scene.py','mtr_project/screening.py','mtr_project/sources.py',
                                                                 'evaluate_candidate_checks.py','trajectory_checks.py','refine_candidate_paths.py']}},
                  [run_dir/'anchored_feasibility.json'],allow_new=not args.cached_only)
            record={'key':key,'clip':item['clip'],'recording_id':item['recording_id'],'split':args.split,
                    'anchor_fraction':fraction,'anchor_seconds':seconds,'sample':sample,'run':run,
                    'annotation_timing':'NOT_USED_OR_ASSUMED; fixed fractions of the full log',
                    'diagnostic_scope':'candidate coverage and limited screening, not confirmed doPlan instruction compliance'}
            records.append(record)
            retain_completed_window(manifest,record,expected)
    print('Completed windows:',len(records),flush=True)

if __name__=='__main__':main()
