"""Record the baseline before opening independent evaluation results."""
import datetime,json
from mtr_project.paths import ROOT,sha256,write_json

def main():
    target=ROOT/'runs/project-v2/baseline-v1/frozen-baseline.json'
    if target.exists():raise ValueError('Baseline already frozen; use a separately versioned experiment')
    config=json.loads((ROOT/'config/project-v2-scenes.json').read_text())
    development={r['recording_id'] for r in config['selected'] if r['split']=='development'}
    evaluation={r['recording_id'] for r in config['selected'] if r['split']=='evaluation'}
    if development & evaluation:raise ValueError('Recording leakage across splits')
    paths=['config/project-v2-scenes.json','scripts/convert_nuplan_mtr.py','scripts/smoke_mtr.py',
           'scripts/export_mtr_candidates.py','scripts/evaluate_candidate_checks.py','scripts/trajectory_checks.py',
           'scripts/refine_candidate_paths.py','scripts/mtr_project/screening.py','scripts/language_selector.py',
           'scripts/mtr_project/language.py','scripts/mtr_project/planner.py','scripts/evaluate_project.py']
    report={'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'files':{p:sha256(ROOT/p) for p in paths},'anchor_fractions':[.2,.5,.8],
            'development_recordings':sorted(development),'evaluation_recordings':sorted(evaluation),
            'selection':'Highest MTR score among candidates passing fixed checks and the explicit action predicate.',
            'scope':'Three held-out recordings, nine fixed windows. Diagnostic action coverage, not aligned doPlan semantic accuracy.',
            'rule':'Do not retune this baseline using evaluation outputs. Alternative methods must be separately named.'}
    write_json(target,report);print(target)

if __name__=='__main__':main()
