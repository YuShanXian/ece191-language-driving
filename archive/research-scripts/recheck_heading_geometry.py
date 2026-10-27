"""Preserve v1 artifacts and rerun cached checks after tangent-estimator correction."""
import shutil
from pathlib import Path
from plot_language_choices import CASES
from evaluate_candidate_checks import evaluate
ROOT=Path(__file__).resolve().parent.parent
for sample,run in CASES:
    out=ROOT/'runs'/run;archive=out/'before-heading-fix'
    archive.mkdir(exist_ok=False)
    for file in ['refined_feasibility.json','language_baseline.json','language-choices.png','recorded-future-audit.json']:
        if (out/file).exists():shutil.copy2(out/file,archive/file)
    evaluate(sample,run,refined=True)
