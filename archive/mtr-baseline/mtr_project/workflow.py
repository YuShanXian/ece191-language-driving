"""Evidence and fail-fast execution for the fixed-fraction offline workflow."""
import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from .paths import sha256,write_json

SPLITS=('development','evaluation')
FRACTIONS=(.2,.5,.8)


def validate_tag(tag):
    if not isinstance(tag,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',tag):
        raise ValueError('Use a simple tag of at most80 letters, digits, hyphens or underscores')
    return tag


def expected_records(config,tag):
    validate_tag(tag);selected=config['selected'];clips=[];recordings={s:set() for s in SPLITS};result={}
    for row in selected:
        clip=row['clip'];split=row['split']
        if split not in SPLITS or not re.fullmatch(r'[A-Za-z0-9_.-]+',clip) or '..' in clip:
            raise ValueError('Invalid scene identity')
        if row['recording_id']!=clip.rsplit('_',2)[0]:raise ValueError('Recording identity differs from clip')
        clips.append(clip);recordings[split].add(row['recording_id'])
    if len(clips)!=len(set(clips)):raise ValueError('Duplicate clip')
    if any(not ids for ids in recordings.values()):raise ValueError('Both splits must be nonempty')
    if recordings['development'] & recordings['evaluation']:raise ValueError('Recording leakage between splits')
    for split in SPLITS:
        result[split]=[]
        for index,row in enumerate(r for r in selected if r['split']==split):
            for fraction in FRACTIONS:
                key=f'{split}-{index:02d}-f{round(fraction*1000):03d}'
                result[split].append({'key':key,'clip':row['clip'],'recording_id':row['recording_id'],'split':split,
                    'anchor_fraction':fraction,'sample':f'project-v2/{tag}/{key}','run':f'project-v2/{tag}/{key}'})
    return result


def validate_manifest(rows,expected):
    if not isinstance(rows,list) or [r['key'] for r in rows]!=[r['key'] for r in expected]:
        raise ValueError('Manifest is missing, duplicated, reordered or contains unexpected windows')
    for row,wanted in zip(rows,expected):
        if any(row.get(key)!=value for key,value in wanted.items()):raise ValueError('Manifest provenance mismatch')


def inspect_data(root,config,tag):
    expected_records(config,tag)
    names=['config/project-v2-scenes.json','references/release_annotationsV1.csv',
        'weights/pretrained_weights/checkpoint_for_val_test.ckpt','data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg']
    records=[]
    for row in config['selected']:
        name=f"data/nuplan/db/{row['clip']}.db";path=root/name
        if path.stat().st_size!=row['bytes']:raise ValueError('Database size differs from source inventory: '+name)
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as conn:
            count,start,end=conn.execute('SELECT COUNT(*),MIN(timestamp),MAX(timestamp) FROM lidar_pc').fetchone()
        if not count or start>=end:raise ValueError('Empty or invalid lidar timeline: '+name)
        records.append({'clip':row['clip'],'lidar_rows':count,'first_timestamp_us':start,'last_timestamp_us':end});names.append(name)
    if tag=='baseline-v1':
        freeze=root/'runs/project-v2/baseline-v1/frozen-baseline.json'
        for name,value in json.loads(freeze.read_text())['files'].items():
            if sha256(root/name)!=value:raise ValueError('Frozen baseline changed: '+name)
        names.append(str(freeze.relative_to(root)))
    return {'source_sha256':{name:sha256(root/name) for name in names},'recordings':records,
        'scope':'Presence, content fingerprints, declared DB sizes and readable lidar timelines; not full sensor alignment certification.'}


def run_steps(root,folder,steps,receipt):
    """Stop on the first failed command and leave its log and durable receipt."""
    target=folder/'workflow.json';receipt['steps']=[];receipt['status']='running';write_json(target,receipt)
    for name,command in steps:
        print('WORKFLOW',name,flush=True);log=folder/(name+'.log');start=time.monotonic()
        try:
            with log.open('w') as stream:
                process=subprocess.run([sys.executable,*command],cwd=root,stdout=stream,stderr=subprocess.STDOUT)
        except Exception as exc:
            receipt.update(status='failed',error=str(exc),failed_step=name);write_json(target,receipt);raise
        receipt['steps'].append({'name':name,'command':command,'returncode':process.returncode,
            'seconds':round(time.monotonic()-start,3),'log':str(log.relative_to(root)),'log_sha256':sha256(log)})
        if process.returncode:
            receipt.update(status='failed',failed_step=name);write_json(target,receipt)
            raise RuntimeError(f'{name} failed; see {log}\n'+log.read_text()[-3000:])
        write_json(target,receipt)


def collect_outputs(root,tag,expected):
    files=[];base=root/'runs/project-v2'/tag
    for split in SPLITS:
        manifest=base/f'{split}-manifest.json';rows=json.loads(manifest.read_text());validate_manifest(rows,expected[split]);files.append(manifest)
        evaluation=base/f'{split}-evaluation.json';report=json.loads(evaluation.read_text())
        validate_manifest([r['scene'] for r in report['windows']],expected[split])
        for entry in report['windows']:
            run=root/'runs'/entry['scene']['run']
            for field,name in [('raw_candidates','internal_0000.npz'),('checks','anchored_feasibility.json')]:
                if sha256(run/name)!=entry['source_hashes'][field]:raise ValueError('Evaluation uses stale outputs: '+entry['scene']['key'])
        files.append(evaluation)
        for row in rows:
            sample=root/'samples'/row['sample'];run=root/'runs'/row['run'];conversion=json.loads((sample/'conversion.json').read_text())
            scenario=(sample/conversion['scenario']).resolve()
            if not scenario.is_relative_to(sample.resolve()):raise ValueError('Scenario escaped sample folder')
            files.extend([sample/'conversion.json',sample/'dataset_mapping.pkl',sample/'dataset_summary.pkl',scenario])
            files.extend(run/name for name in ['internal_0000.npz','refined_v2_candidates.npz','anchored_feasibility.json'])
    return {str(p.relative_to(root)):sha256(p) for p in files}
