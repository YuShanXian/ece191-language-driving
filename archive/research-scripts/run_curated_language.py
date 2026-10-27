import json
from mtr_project.paths import ROOT,sha256,write_json
from run_project_pipeline import stage
source=ROOT/'runs/project-v3/curated-turn-windows/validated-20261019T072937Z/manifest.json'
plan=json.loads(source.read_text());base=ROOT/'runs/project-v3/language-choice-v1';base.mkdir(parents=True,exist_ok=True)
checkpoint=ROOT/'weights/pretrained_weights/checkpoint_for_val_test.ckpt';records=[]
for row in plan['windows']:
 sample=row['sample'];folder=ROOT/'samples'/sample
 for name,digest in row['sample_sha256'].items():
  if sha256(ROOT/name)!=digest:raise ValueError('Sample changed '+name)
 run='project-v3/language-choice-v1/'+f"{row['number']:02d}-{row['action']}";out=ROOT/'runs'/run;logs=base/'execution'/out.name
 stage('infer',['scripts/export_mtr_candidates.py','--checkpoint',str(checkpoint),'--data',str(folder),'--output',str(out),'--ego-only'],logs,{'manifest':sha256(source),'checkpoint':sha256(checkpoint),'export':sha256(ROOT/'scripts/export_mtr_candidates.py'),'smoke':sha256(ROOT/'scripts/smoke_mtr.py')},[out/'internal_0000.npz'])
 stage('check',['scripts/screen_project_scene.py','--sample',sample,'--run',run,'--preserve-start-ambiguity'],logs,{'raw':sha256(out/'internal_0000.npz'),'code':{p:sha256(ROOT/'scripts'/p) for p in ['trajectory_checks.py','mtr_project/screening.py','screen_project_scene.py','evaluate_candidate_checks.py','refine_candidate_paths.py']}},[out/'ambiguity_aware_feasibility.json',out/'refined_v2_candidates.npz'])
 records.append({**row,'run':run});write_json(base/'manifest.json',{'source':str(source.relative_to(ROOT)),'source_sha256':sha256(source),'windows':records})
print('Completed',len(records),flush=True)
