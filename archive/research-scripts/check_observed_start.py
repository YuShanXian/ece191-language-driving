"""Add a past-only road-node constraint without redoing the neural model."""
import json,pickle
import numpy as np
from pathlib import Path
from collections import Counter
from evaluate_candidate_checks import load_graph
from plot_language_choices import CASES
ROOT=Path(__file__).resolve().parent.parent
for sample,run in CASES:
    out=ROOT/'runs'/run;folder=ROOT/'samples'/sample
    conv=json.loads((folder/'conversion.json').read_text())
    with (folder/conv['scenario']).open('rb') as f:ego=pickle.load(f)['tracks']['ego']['state']
    graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'])
    history=graph.match(ego['position'][:21,:2],float(ego['heading'][0]))
    anchor=history['node_sequence'][-1] if history['matched'] else None
    data=np.load(out/'refined_v2_candidates.npz')['world_xy'];center=np.load(out/'internal_0000.npz')['center']
    report=json.loads((out/'refined_v2_feasibility.json').read_text())
    for row,xy in zip(report['candidates'],data):
        points=np.vstack([center[:2],xy])
        route=graph.match(points,float(center[6]),start_nodes={anchor}) if anchor else {'matched':False,'failure':'unresolved_observed_start'}
        graph.settled_lane_changes(route,points,float(center[6]),float(center[3]),float(center[4]))
        row['route_before_start_constraint']=row['route'];row['route']=route
        row['rejected_by']=[r for r in row['rejected_by'] if r!='road_route']
        if not route['matched']:row['rejected_by'].append('observed_start_road_route')
        row['passes_current_checks']=not row['rejected_by']
    rows=report['candidates'];summary=report['summary']
    summary.update(past_only_start_node=anchor,observed_history_route=history,
                   passed_candidates=[r['candidate'] for r in rows if r['passes_current_checks']],
                   rejection_counts=dict(Counter(x for r in rows for x in r['rejected_by'])),
                   matched_lane_change_candidates=[r['candidate'] for r in rows if r['route'].get('lane_changes')],
                   matched_turn_candidates=[r['candidate'] for r in rows if r['route'].get('turns')])
    summary['start_constraint_scope']='Single best history map match, not a probabilistic lane-localization guarantee.'
    (out/'anchored_feasibility.json').write_text(json.dumps(report,indent=2))
    print(run,'past-only start',anchor,'passed',summary['passed_candidates'],flush=True)
