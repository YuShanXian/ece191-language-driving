"""Audit saved evidence directly; no inference or claims of fresh-install success."""
import json
from functools import lru_cache
import numpy as np
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.language import parse_instruction
from language_selector import action_matches


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def read(path):return json.loads(path.read_text())


def require(condition,message):
    if not condition:raise ValueError(message)


def audit():
    base=ROOT/'runs/project-v2/baseline-v1';freeze=read(base/'frozen-baseline.json');evidence={};checks=[]
    def source(path):evidence[str(path.relative_to(ROOT))]=digest(path)
    source(base/'frozen-baseline.json')
    for name,expected in freeze['files'].items():require(digest(ROOT/name)==expected,'Frozen source changed: '+name)
    checks.append({'name':'frozen_baseline','files':len(freeze['files'])})
    split_recordings={}
    for split in ['development','evaluation']:
        manifest_path=base/f'{split}-manifest.json';report_path=base/f'{split}-evaluation.json'
        manifest=read(manifest_path);report=read(report_path);source(manifest_path);source(report_path)
        require(len(manifest)==9 and len(report['windows'])==9,'Incomplete baseline split')
        require(len({r['key'] for r in manifest})==9,'Duplicate baseline window')
        lookup={r['scene']['key']:r for r in report['windows']}
        split_recordings[split]={r['recording_id'] for r in manifest}
        require(len(split_recordings[split])==3,'Expected three recordings per split')
        passing=0
        for entry in manifest:
            require(entry['recording_id']==entry['clip'].rsplit('_',2)[0],'Recording identity mismatch')
            result=lookup[entry['key']];folder=ROOT/'runs'/entry['run'];raw_path=folder/'internal_0000.npz';screen_path=folder/'anchored_feasibility.json'
            require(digest(raw_path)==result['source_hashes']['raw_candidates'],'Baseline predictions changed')
            require(digest(screen_path)==result['source_hashes']['checks'],'Baseline check report changed')
            raw=np.load(raw_path);derived=np.load(folder/'refined_v2_candidates.npz')['world_xy'];screen=read(screen_path)
            require(raw['world_xy'].shape==(64,60,2) and derived.shape==(64,60,2),'Unexpected trajectory dimensions')
            require(np.isfinite(raw['world_xy']).all() and np.isfinite(derived).all() and np.isfinite(raw['scores']).all(),'Non-finite predictions')
            require([r['candidate'] for r in screen['candidates']]==list(range(1,65)),'Candidate identifiers inconsistent')
            count=sum(r['passes_current_checks'] for r in screen['candidates']);passing+=count
            require(count==result['passing_count'],'Saved evaluation count disagrees with candidate checks')
            for path in [raw_path,screen_path,folder/'refined_v2_candidates.npz']:source(path)
        require(passing==report['summary']['passing_candidates'],'Baseline summary count inconsistent')
        checks.append({'name':split+'_baseline','windows':9,'recordings':3,'passing_candidates':passing})
    require(not(split_recordings['development']&split_recordings['evaluation']),'Recording leaks across data splits')
    checks.append({'name':'recording_split_disjoint','passed':True})
    future_path=ROOT/'runs/project-v2/future-mask-audit/summary.json';future=read(future_path);source(future_path)
    require(len(future['results'])==3,'Future audit missing windows')
    for row in future['results']:
        raw=base/row['scene']/'internal_0000.npz';masked=ROOT/'runs/project-v2/future-mask-audit'/row['scene']/'internal_0000.npz'
        require(digest(raw)==row['source_sha256'],'Future audit refers to another source prediction')
        original=np.load(raw);perturbed=np.load(masked)
        require(all(np.array_equal(original[k],perturbed[k]) for k in ['world_xy','scores','selected_indices']),'Saved future-masked predictions differ')
        source(masked)
    checks.append({'name':'saved_future_mask_array_equality','windows':3,'scope':'Rechecked saved outputs, not a new GPU rerun or universal leakage proof.'})
    for tag in ['annotation-sequence-v1','second-annotation-v1']:
        folder=ROOT/'runs/project-v2'/tag;spec=read(folder/'sequence-config.json');manifest=read(folder/'sequence-manifest.json')
        require([r['video_frame'] for r in manifest]==spec['frames'],'Actual annotation sequence incomplete or reordered')
        require(digest(ROOT/'weights/pretrained_weights/checkpoint_for_val_test.ckpt')==spec['fingerprints']['checkpoint'],'Weights changed')
        source(folder/'sequence-config.json');source(folder/'sequence-manifest.json')
        reports=list(folder.glob('sequence-report*.json'));require(bool(reports),'Missing persistent sequence evaluation')
        program=parse_instruction(spec['instruction']);require(program['status']=='parsed','Actual annotation no longer parses')
        for path in reports:
            report=read(path);source(path)
            require([r['timestamp_us'] for r in report['checkpoints']]==[r['timestamp_us'] for r in manifest],'Sequence timestamps differ')
            require(report['instruction']==spec['instruction'],'Sequence instruction changed')
            for row in report['checkpoints']:
                screen_path=ROOT/'runs'/row['run']/'anchored_feasibility.json'
                require(digest(screen_path)==row['screen_sha256'],'Sequence candidate screen changed')
                source(screen_path);selected=row['selection']['candidate']
                if selected is not None:
                    require(row['selection']['stage']['state']=='active','Proposal issued outside active stage')
                    candidate=read(screen_path)['candidates'][selected-1];action=row['selection']['stage']['action']
                    require(candidate['passes_current_checks'] and action_matches(candidate,action,row['speed_mps']),'Selected path does not pass or match stage')
        checks.append({'name':tag,'windows':len(manifest),'sequence_reports':len(reports),'selection_semantics_rechecked':True})
    for folder in sorted((ROOT/'runs/project-v2/video-alignment').iterdir()):
        viewer=folder/'viewer-alignment.json'
        if not viewer.exists():continue
        data=read(viewer);source(viewer)
        for key,path in {'gps':ROOT/'data/doplan'/data['clip']/'gps.csv','database':ROOT/'data/nuplan/db'/(data['clip']+'.db'),'release':ROOT/'references/release_annotationsV1.csv','camera_audit':folder/'camera-lookup-audit.json','video_audit':folder/'video-audit.json'}.items():
            require(digest(path)==data['source_sha256'][key],'Alignment source changed: '+str(path));source(path)
        for video in data['videos']:require(digest(ROOT/video['file'])==video['sha256'],'Decoded video changed')
        require(len(data['frame_mapping'])==data['video_frames'],'Viewer frame count mismatch')
        require(all(not a['usable_for_confirmed_language_evaluation'] for a in data['annotations']),'Conditional alignment mislabeled as confirmed truth')
        checks.append({'name':'conditional_alignment','clip':data['clip'],'video_frames':data['video_frames'],'gps_rows':data['gps_rows']})
    return {'status':'saved_offline_evidence_checked','checks':checks,'source_sha256':evidence,'auditor_sha256':sha256(__file__),
        'limitations':['Fresh-machine restore and closed-loop execution are not tested.','Some legacy receipts lack creation-time output hashes; current shape checks do not accessenticate their historical derived arrays.','Video alignment is conditional; independent raw-image timing attestation is absent.','Map connector legality and complete vehicle/actor dynamics are not established.','This checks evidence consistency, not natural-language accuracy or real-world safety.']}


def main():
    result=audit();write_json(ROOT/'runs/project-v2/verification/saved-evidence.json',result)
    print(json.dumps({'status':result['status'],'checks':result['checks']},indent=2))


if __name__=='__main__':main()
