"""Compare a causal acceleration boundary on all existing windows, no new MTR runs."""
import json
from pathlib import Path
from plot_language_choices import CASES
from evaluate_candidate_checks import evaluate
ROOT=Path(__file__).resolve().parent.parent
results=[]
for sample,run in CASES:
    results.append(evaluate(sample,run,refined=True,boundary_acceleration=True))
(ROOT/'runs/language-baseline/acceleration-boundary-summary.json').write_text(json.dumps(results,indent=2))
