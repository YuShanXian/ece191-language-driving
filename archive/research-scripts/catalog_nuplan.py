"""Index official archive metadata and choose independent annotated logs before inference.

Downloads only ZIP central-directory ranges. Actual data fetch is a separate step.
"""
import argparse
import concurrent.futures
import json
import zipfile
import hashlib
from pathlib import PurePosixPath
from inspect_remote_nuplan import Remote, BASE
from mtr_project.paths import ROOT, write_json

def index_archive(name):
    cache = ROOT/'runs/project-v2/catalog'/f'{name}.json'
    if cache.exists():
        return json.loads(cache.read_text())
    with zipfile.ZipFile(Remote(name)) as archive:
        rows = [{'archive': name, 'member': x.filename, 'clip': PurePosixPath(x.filename).stem,
                 'bytes': x.file_size, 'compressed_bytes': x.compress_size, 'crc32': x.CRC}
                for x in archive.infolist() if x.filename.endswith('.db')]
    write_json(cache, {'source': BASE+name, 'members': rows})
    print(name, len(rows), 'database entries', flush=True)
    return {'source': BASE+name, 'members': rows}

def main():
    p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=6);args=p.parse_args()
    sources=[f'nuplan-v1.1_train_vegas_{i}.zip' for i in range(1,7)]
    members=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        for report in executor.map(index_archive, sources):
            members.extend(report['members'])
    annotations=json.loads((ROOT/'runs/project-v2/inventory/annotations.json').read_text())['clips']
    candidates=[]
    for item in members:
        group=annotations.get(item['clip'])
        if not group or item['bytes']>300*1024*1024:continue
        supported=[r for r in group['annotations'] if r['parse']['status']=='parsed']
        if not supported:continue
        item.update(recording_id=group['recording_id'],supported_annotations=supported)
        candidates.append(item)
    # Deterministic preregistration: prioritize annotation coverage, then hash.
    # Never select a log based on its model output or evaluation metrics.
    candidates.sort(key=lambda r:(-len(r['supported_annotations']),hashlib.sha256(r['clip'].encode()).hexdigest()))
    selected=[];recordings={'2021.06.09.12.39.51_veh-26'}
    for item in candidates:
        item['actions']=sorted({s['action'] for a in item['supported_annotations'] for s in a['parse']['stages']})
    action_counts={'development':{},'evaluation':{}}
    while len(selected)<args.count:
        split='development' if len(selected)<args.count//2 else 'evaluation'
        eligible=[x for x in candidates if x['recording_id'] not in recordings]
        if not eligible:break
        item=min(eligible,key=lambda r:(min(action_counts[split].get(a,0) for a in r['actions']),
                                       -len(r['supported_annotations']),hashlib.sha256(r['clip'].encode()).hexdigest()))
        item['split']='development' if len(selected)<args.count//2 else 'evaluation'
        selected.append(item);recordings.add(item['recording_id'])
        for action in item['actions']:action_counts[split][action]=action_counts[split].get(action,0)+1
    report={'selection_rule':'distinct recordings; balance supported action categories within split, then annotation count, then SHA256 clip ID; max 300 MiB per DB; selected before inference',
            'candidate_clips':len(candidates),'selected':selected,
            'total_bytes':sum(x['bytes'] for x in selected),
            'limitation':'Annotation timing for these logs remains unverified without GPS/video export parity; independent scene diagnostics are valid but not confirmed language-label evaluation.'}
    write_json(ROOT/'config/project-v2-scenes.json',report)
    print(json.dumps({'selected':[{k:r[k] for k in ('clip','split','actions','bytes')} for r in selected], 'total_bytes':report['total_bytes']},indent=2),flush=True)

if __name__=='__main__':main()
