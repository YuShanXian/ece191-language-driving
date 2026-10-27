"""Exploratory MTR checkpoints within one aligned doPlan annotation window."""
import argparse,json,re
from mtr_project.paths import ROOT,sha256,write_json
from run_project_pipeline import stage
from mtr_project.manifests import read_manifest,retain_completed_window


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default='annotation-sequence-v1')
    parser.add_argument('--spec',help='Project-relative JSON specifying clip, annotation, evidence and frames')
    parser.add_argument('--limit',type=int);args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.tag):raise ValueError('Simple tag required')
    if args.limit is not None and args.limit<1:raise ValueError('Limit must be positive')
    custom={}
    if args.spec:
        spec_file=(ROOT/args.spec).resolve()
        if not spec_file.is_relative_to(ROOT):raise ValueError('Spec must stay in project')
        custom=json.loads(spec_file.read_text())
    clip=custom.get('clip','2021.06.09.12.39.51_veh-26_05332_05540')
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+',clip) or '..' in clip:raise ValueError('Invalid clip')
    evidence_path=ROOT/'runs/project-v2/video-alignment'/clip/custom.get('evidence','alignment-evidence.json')
    if not evidence_path.resolve().is_relative_to(ROOT):raise ValueError('Evidence must stay in project')
    evidence=json.loads(evidence_path.read_text())
    annotation=next(a for a in evidence['annotations'] if a['annotation']['annotation_id']==custom.get('annotation_id','doplan_006160'))
    if not annotation['usable_for_window_level_exploration']:raise ValueError('Window mapping unresolved')
    label=annotation['annotation'];anchors=custom.get('frames',[425,600,700,800,900,950,975,1000])
    if not anchors or any(not isinstance(f,int) for f in anchors) or sorted(set(anchors))!=anchors:raise ValueError('Increasing unique integer frame anchors required')
    expected=[f'{label["annotation_id"]}-f{f:04d}' for f in anchors]
    manifest=ROOT/'runs/project-v2'/args.tag/'sequence-manifest.json'
    read_manifest(manifest,expected)
    checkpoint=ROOT/'weights/pretrained_weights/checkpoint_for_val_test.ckpt'
    db=ROOT/'data/nuplan/db'/f'{clip}.db';map_file=ROOT/'data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg'
    fingerprint={'db':sha256(db),'map':sha256(map_file),'checkpoint':sha256(checkpoint),'alignment':sha256(evidence_path)}
    output=ROOT/'runs/project-v2'/args.tag;output.mkdir(parents=True,exist_ok=True)
    spec={'frames':anchors,'annotation_id':label['annotation_id'],'instruction':label['instruction'],
          'fingerprints':fingerprint,'selection_scope':'Checkpoints chosen after viewing the example; exploratory, not a held-out evaluation.',
          'command_issue_time_known':False}
    if custom:spec.update(configuration=custom,configuration_sha256=sha256(spec_file))
    spec_path=output/'sequence-config.json'
    if spec_path.exists() and json.loads(spec_path.read_text())!=spec:raise ValueError('Use a new tag for changed inputs')
    write_json(spec_path,spec);records=[]
    for frame in anchors:
        if args.limit is not None and len(records)>=args.limit:break
        if not label['start_frame']<=frame<label['end_frame']:raise ValueError('Anchor outside annotation window')
        timestamp=evidence['frame_mapping'][frame]['timestamp_us'];key=f'{label["annotation_id"]}-f{frame:04d}'
        sample=f'project-v2/{args.tag}/{key}';run=sample
        sample_dir=ROOT/'samples'/sample;run_dir=ROOT/'runs'/run;logdir=output/'execution'/key
        stage('convert',['scripts/convert_nuplan_mtr.py','--db',str(db),'--timestamp-us',str(timestamp),'--output',str(sample_dir)],
              logdir,{'db':fingerprint['db'],'map':fingerprint['map'],'converter':sha256(ROOT/'scripts/convert_nuplan_mtr.py')},
              [sample_dir/'conversion.json'])
        conversion=json.loads((sample_dir/'conversion.json').read_text())
        if conversion['current_timestamp_us']!=timestamp:raise ValueError('Converter did not retain the exact GPS timestamp')
        stage('infer',['scripts/export_mtr_candidates.py','--checkpoint',str(checkpoint),'--data',str(sample_dir),
                       '--output',str(run_dir),'--ego-only'],logdir,
              {'conversion':sha256(sample_dir/'conversion.json'),'scenario':sha256(sample_dir/conversion['scenario']),
               'checkpoint':fingerprint['checkpoint'],'smoke':sha256(ROOT/'scripts/smoke_mtr.py'),
               'export':sha256(ROOT/'scripts/export_mtr_candidates.py')},[run_dir/'internal_0000.npz'])
        stage('check',['scripts/screen_project_scene.py','--sample',sample,'--run',run],logdir,
              {'candidates':sha256(run_dir/'internal_0000.npz'),
               'sources':{p:sha256(ROOT/'scripts'/p) for p in ['screen_project_scene.py','mtr_project/screening.py',
                   'mtr_project/sources.py','evaluate_candidate_checks.py','trajectory_checks.py','refine_candidate_paths.py']}},
              [run_dir/'anchored_feasibility.json',run_dir/'refined_v2_candidates.npz'])
        records.append({'key':key,'clip':clip,'video_frame':frame,'timestamp_us':timestamp,
                        'gps_elapsed_seconds':(timestamp-evidence['frame_mapping'][0]['timestamp_us'])/1e6,
                        'sample':sample,'run':run,'instruction':label['instruction'],
                        'split':'aligned-window exploration','screen_sha256':sha256(run_dir/'anchored_feasibility.json')})
        retain_completed_window(manifest,records[-1],expected)
    print('Finished checkpoints:',len(records),flush=True)


if __name__=='__main__':main()
