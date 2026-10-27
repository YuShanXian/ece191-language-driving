"""Audit development-set ablation from immutable, cached MTR predictions."""
import json
import numpy as np
from language_selector import action_matches
from mtr_project.paths import ROOT,sha256,write_json


def main():
    manifest_path=ROOT/'runs/project-v2/baseline-v1/development-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    methods={'baseline':'baseline-v1','connector_geometry':'connector-route-development-v1','map_tail':'map-tail-development-v1'}
    actions=['lane_change_left','lane_change_right'];rows=[];sources={str(manifest_path.relative_to(ROOT)):sha256(manifest_path)}
    for entry in manifest:
        conv_path=ROOT/'samples'/entry['sample']/'conversion.json'
        conv=json.loads(conv_path.read_text());row={'key':entry['key'],'clip':entry['clip'],'methods':{}}
        reports={};arrays={}
        for method,tag in methods.items():
            folder=ROOT/'runs/project-v2'/tag/entry['key'];path=folder/'anchored_feasibility.json'
            report=json.loads(path.read_text());reports[method]=report
            for source in [path,folder/'internal_0000.npz',folder/'refined_v2_candidates.npz',conv_path]:sources[str(source.relative_to(ROOT))]=sha256(source)
            arrays[method]=np.load(folder/'refined_v2_candidates.npz')['world_xy']
            if method=='baseline':raw_hash=sha256(folder/'internal_0000.npz');raw=np.load(folder/'internal_0000.npz')['world_xy']
            elif sha256(folder/'internal_0000.npz')!=raw_hash:raise ValueError('Raw MTR predictions were changed')
            matching={action:[r['candidate'] for r in report['candidates'] if r['passes_current_checks'] and action_matches(r,action,conv['current_speed_mps'])] for action in actions}
            row['methods'][method]={'passing_count':sum(r['passes_current_checks'] for r in report['candidates']),
                'matching_by_action':matching,'selected_by_action':{a:max((r for r in report['candidates'] if r['candidate'] in matching[a]),key=lambda r:(r['score'],-r['candidate']),default={'candidate':None})['candidate'] for a in actions}}
        experiment=reports['map_tail']['map_tail_experiment'];modified=experiment['modified_candidates']
        if not np.array_equal(arrays['baseline'],arrays['connector_geometry']):raise ValueError('Geometry-only variant changed a trajectory')
        if not np.array_equal(arrays['connector_geometry'][:,:30],arrays['map_tail'][:,:30]):raise ValueError('Tail refinement changed the first 3 seconds')
        details=[]
        for i in range(len(raw)):
            if i+1 not in modified:
                if not np.array_equal(arrays['connector_geometry'][i],arrays['map_tail'][i]):raise ValueError('Unreported candidate change')
                continue
            candidate=reports['map_tail']['candidates'][i];deviation=float(np.linalg.norm(arrays['map_tail'][i]-raw[i],axis=1).max())
            if not candidate['passes_current_checks'] or deviation>1.:raise ValueError('Modified proposal violates declared checks or deviation bound')
            if not any(i+1 in row['methods']['map_tail']['matching_by_action'][a] for a in actions):raise ValueError('Modified proposal does not match the requested single merge')
            details.append({'candidate':i+1,'signed_tail_shift_m':candidate['refinement']['signed_shift_m'],'max_deviation_from_raw_m':deviation})
        row['modifications']=details;row['trial_count']=len(experiment['trials']);rows.append(row)
    summary={method:{'passing_candidates':sum(r['methods'][method]['passing_count'] for r in rows),
        'windows_with_any_passing':sum(r['methods'][method]['passing_count']>0 for r in rows),
        'windows_with_matching_action':{a:sum(bool(r['methods'][method]['matching_by_action'][a]) for r in rows) for a in actions}} for method in methods}
    result={'recordings':len(set(r['clip'] for r in rows)),'windows':len(rows),'summary':summary,'windows_detail':rows,
        'audit':{'raw_predictions_identical':True,'geometry_variant_paths_identical':True,'first_three_seconds_preserved':True,'all_modified_paths_screened_and_within_one_meter_of_raw':True},
        'source_sha256':sources,'generator_sha256':sha256(__file__),
        'scope':'Three additional development recordings, fixed 20/50/80% anchors. Rules developed using doplan_006160; this is not a blind evaluation. Diagnostic commands, not semantic accuracy. Geometry does not establish legal lane crossing or closed-loop feasibility.'}
    write_json(ROOT/'runs/project-v2/map-tail-development-v1/comparison.json',result)
    print(json.dumps({'recordings':result['recordings'],'windows':len(rows),'summary':summary,'modifications':{r['key']:r['modifications'] for r in rows if r['modifications']}},indent=2))


if __name__=='__main__':main()
