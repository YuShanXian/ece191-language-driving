"""Run the registered new-recording challenge using unchanged cached-stage machinery."""
import argparse,json
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.manifests import read_manifest,retain_completed_window
from run_project_pipeline import stage


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cached-only',action='store_true');parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    if args.limit is not None and args.limit<1:parser.error('Positive limit required')
    plan_path=ROOT/'runs/project-v2/turn-challenge-v1/window-plan.json';plan=json.loads(plan_path.read_text())
    for mapping in [plan['source_sha256'],plan['implementation_sha256']]:
        for name,expected in mapping.items():
            if sha256(ROOT/name)!=expected:raise ValueError('Registered dependency changed: '+name)
    base=plan_path.parent;manifest=base/'manifest.json';expected=[r['key'] for r in plan['windows']];read_manifest(manifest,expected)
    checkpoint=ROOT/'weights/pretrained_weights/checkpoint_for_val_test.ckpt'
    fixed={'window_plan_sha256':sha256(plan_path),'checkpoint':plan['source_sha256'][str(checkpoint.relative_to(ROOT))]}
    for number,row in enumerate(plan['windows']):
        if args.limit is not None and number>=args.limit:break
        sample=ROOT/'samples'/row['sample'];run=ROOT/'runs'/row['run'];logs=base/'execution'/row['key'];db=ROOT/'data/nuplan/db'/(row['clip']+'.db')
        stage('convert',['scripts/convert_nuplan_mtr.py','--db',str(db),'--timestamp-us',str(row['timestamp_us']),'--output',str(sample)],logs,
              fixed,[sample/'conversion.json'],allow_new=not args.cached_only)
        stage('infer',['scripts/export_mtr_candidates.py','--checkpoint',str(checkpoint),'--data',str(sample),'--output',str(run),'--ego-only'],logs,
              {**fixed,'conversion':sha256(sample/'conversion.json')},[run/'internal_0000.npz'],allow_new=not args.cached_only)
        stage('check',['scripts/screen_project_scene.py','--sample',row['sample'],'--run',row['run']],logs,
              {**fixed,'candidates':sha256(run/'internal_0000.npz')},[run/'anchored_feasibility.json',run/'refined_v2_candidates.npz'],allow_new=not args.cached_only)
        retain_completed_window(manifest,row,expected)
        screen=json.loads((run/'anchored_feasibility.json').read_text())
        print(json.dumps({'window':row['key'],'completed':number+1,'total':len(expected),'passing_candidates':sum(c['passes_current_checks'] for c in screen['candidates'])}),flush=True)
    completed=read_manifest(manifest,expected)
    for mapping in [plan['source_sha256'],plan['implementation_sha256']]:
        for name,expected_hash in mapping.items():
            if sha256(ROOT/name)!=expected_hash:raise ValueError('Dependency changed during challenge: '+name)
    write_json(base/'progress.json',{'status':'completed' if len(completed)==len(expected) else 'partial','completed_windows':len(completed),'expected_windows':len(expected),'window_plan_sha256':sha256(plan_path)})


if __name__=='__main__':main()
