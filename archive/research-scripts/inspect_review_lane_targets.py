import json,numpy as np
from mtr_project.paths import ROOT
from evaluate_candidate_checks import load_graph
base=ROOT/'runs/project-v3/language-choice-v1/report-reviewed'
for w in json.loads((base/'evaluation.json').read_text())['windows']:
 c=json.loads((ROOT/'samples'/w['source_window']['sample']/'conversion.json').read_text())
 s=json.loads((ROOT/'runs'/w['source_window']['run']/'ambiguity_aware_feasibility.json').read_text())['summary']
 g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map'])
 print(w['number'],[(k,g.nodes[k].kind,g.edges.get(k,{})) for k in s['past_only_start_nodes']],flush=True)
