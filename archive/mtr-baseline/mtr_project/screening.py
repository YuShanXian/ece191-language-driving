"""Apply the v1 screens with a present/past-only initial-lane constraint."""
import json
import pickle
from collections import Counter
import numpy as np
from .paths import ROOT, write_json
from evaluate_candidate_checks import evaluate, load_graph

def screen(sample, run, preserve_start_ambiguity=False):
    evaluate(sample, run, refined=True, boundary_acceleration=True)
    folder=ROOT/'samples'/sample;out=ROOT/'runs'/run
    conv=json.loads((folder/'conversion.json').read_text())
    with (folder/conv['scenario']).open('rb') as stream:
        ego=pickle.load(stream)['tracks']['ego']['state']
    graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv.get('source_map'))
    history=graph.match(ego['position'][:21,:2],float(ego['heading'][0]),return_end_states=preserve_start_ambiguity)
    anchor=history['node_sequence'][-1] if history['matched'] else None
    anchors={r['node'] for r in history.get('viable_end_states',[])} if preserve_start_ambiguity else ({anchor} if anchor else set())
    data=np.load(out/'refined_v2_candidates.npz')['world_xy']
    center=np.load(out/'internal_0000.npz')['center']
    report=json.loads((out/'refined_v2_feasibility.json').read_text())
    for row,xy in zip(report['candidates'],data):
        points=np.vstack([center[:2],xy])
        route=graph.match(points,float(center[6]),start_nodes=anchors) if anchors else {'matched':False,'failure':'unresolved_observed_start'}
        graph.settled_lane_changes(route,points,float(center[6]),float(center[3]),float(center[4]))
        row['route_before_start_constraint']=row['route'];row['route']=route
        row['rejected_by']=[r for r in row['rejected_by'] if r!='road_route']
        if not route['matched']:row['rejected_by'].append('observed_start_road_route')
        row['passes_current_checks']=not row['rejected_by']
    rows=report['candidates']
    report['summary'].update(past_only_start_nodes=sorted(anchors),start_constraint_mode='all_history_viable' if preserve_start_ambiguity else 'legacy_single_best',past_only_start_node=anchor,observed_history_route=history,
        passed_candidates=[r['candidate'] for r in rows if r['passes_current_checks']],
        rejection_counts=dict(Counter(x for r in rows for x in r['rejected_by'])),
        source_database=conv['source_db'],source_map=conv['source_map'])
    write_json(out/('ambiguity_aware_feasibility.json' if preserve_start_ambiguity else 'anchored_feasibility.json'),report)
    return report
