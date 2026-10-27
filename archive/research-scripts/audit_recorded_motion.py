"""Evaluation-only recorded futures. Never imported by inference or selection."""
import json,pickle
import numpy as np
from pathlib import Path
from evaluate_candidate_checks import load_graph,current_obstacles
from trajectory_checks import collision_check,motion_check
from plot_language_choices import CASES
ROOT=Path(__file__).resolve().parent.parent
reports=[]
for sample,run in CASES:
    folder=ROOT/'samples'/sample;out=ROOT/'runs'/run
    conv=json.loads((folder/'conversion.json').read_text())
    with (folder/conv['scenario']).open('rb') as f:scenario=pickle.load(f)
    ego=scenario['tracks']['ego']['state'];xy=ego['position'][20:,:2]
    heading=float(ego['heading'][20]);length=float(ego['length'][20]);width=float(ego['width'][20])
    graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'])
    route=graph.match(xy,heading);graph.settled_lane_changes(route,xy,heading,length,width)
    obstacles,bad=current_obstacles(conv)
    collision=collision_check(xy,heading,length,width,obstacles)
    errors={}
    for label,file in [('raw','internal_0000.npz'),('refined','refined_candidates.npz')]:
        pred=np.load(out/file)['world_xy']
        distance=np.linalg.norm(pred-xy[None,1:],axis=-1)
        errors[label]={'ade_m':distance.mean(axis=1).tolist(),'fde_m':distance[:,-1].tolist(),
                       'oracle_min_ade_m':float(distance.mean(axis=1).min()),
                       'oracle_min_fde_m':float(distance[:,-1].min())}
    report={'sample':sample,'run':run,'scope':'Recorded future for offline evaluation ONLY; oracle errors are not deployable selection.',
            'recorded_route':route,'recorded_motion':motion_check(xy,ego['velocity'][20]),
            'recorded_path_under_current_CV_collision_check':collision,
            'interpretation':'A CV collision on the recorded path can indicate extrapolation mismatch or box/margin issues; not proof of a real recorded collision.',
            'prediction_errors':errors}
    (out/'recorded-future-audit.json').write_text(json.dumps(report,indent=2))
    reports.append(report)
    print(json.dumps({'run':run,'matched':route.get('matched'),'changes':route.get('lane_changes'),
                      'turns':route.get('turns'),'CV_on_recorded':collision,
                      'raw_oracle_ADE':errors['raw']['oracle_min_ade_m']}),flush=True)
(ROOT/'runs/language-baseline/recorded-future-audit.json').write_text(json.dumps(reports,indent=2))
