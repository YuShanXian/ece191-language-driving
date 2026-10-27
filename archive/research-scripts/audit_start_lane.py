"""Infer current road node from observed history only and audit future routes."""
import json,pickle
import numpy as np
from pathlib import Path
from evaluate_candidate_checks import load_graph
from plot_language_choices import CASES
ROOT=Path(__file__).resolve().parent.parent
reports=[]
for sample,run in CASES:
    folder=ROOT/'samples'/sample;out=ROOT/'runs'/run
    conv=json.loads((folder/'conversion.json').read_text())
    with (folder/conv['scenario']).open('rb') as f:ego=pickle.load(f)['tracks']['ego']['state']
    graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'])
    past=graph.match(ego['position'][:21,:2],float(ego['heading'][0]))
    anchor=past['node_sequence'][-1] if past['matched'] else None
    rows=json.loads((out/'refined_v2_feasibility.json').read_text())['candidates']
    disagreements=[r['candidate'] for r in rows if r['route'].get('matched') and r['route']['node_sequence'][0]!=anchor]
    report={'run':run,'observed_history_route':past,'past_only_current_node':anchor,
            'candidate_start_disagreements':disagreements,
            'passed_candidates_with_disagreement':[r['candidate'] for r in rows if r['passes_current_checks'] and r['candidate'] in disagreements],
            'scope':'Causal best-map-match estimate; ambiguous junction geometry may still require uncertainty handling.'}
    (out/'start-lane-audit.json').write_text(json.dumps(report,indent=2));reports.append(report)
    print(json.dumps({k:v for k,v in report.items() if k!='observed_history_route'}),flush=True)
(ROOT/'runs/language-baseline/start-lane-audit.json').write_text(json.dumps(reports,indent=2))
