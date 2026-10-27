"""Compare identical cached candidate pools. No claims of language-ground-truth accuracy."""
import argparse
import json
import pickle
from collections import Counter
import numpy as np
from mtr_project.paths import ROOT,write_json,sha256
from mtr_project.metrics import trajectory_error,summarize_optional
from mtr_project.annotations import load_release, inventory
from mtr_project.language import parse_instruction as parse_v2
from language_selector import select,parse_instruction as parse_v1

INSTRUCTIONS=['Keep the lane.','Go straight.','Slow down.','Stop.','Remain stopped.',
              'Merge to the left lane.','Merge to the right lane.','Turn left.','Turn right.']

def evaluate_window(record):
    folder=ROOT/'samples'/record['sample'];out=ROOT/'runs'/record['run']
    conversion=json.loads((folder/'conversion.json').read_text())
    cached=np.load(out/'internal_0000.npz')
    raw=cached['world_xy'];refined=np.load(out/'refined_v2_candidates.npz')['world_xy']
    report=json.loads((out/'anchored_feasibility.json').read_text());rows=report['candidates']
    # Selection completes BEFORE opening the saved future used by evaluation.
    choices=[{'instruction':text,**select(text,rows,conversion['current_speed_mps'])} for text in INSTRUCTIONS]
    checked=[r for r in rows if r['passes_current_checks']]
    high=int(np.argmax(cached['scores']))
    filtered=max(checked,key=lambda r:r['score'])['candidate']-1 if checked else None
    with (folder/conversion['scenario']).open('rb') as stream:scenario=pickle.load(stream)
    state=scenario['tracks']['ego']['state']
    future=state['position'][21:81,:2];valid=state['valid'][21:81]>0
    raw_errors=[trajectory_error(p,future,valid) for p in raw]
    refined_errors=[trajectory_error(p,future,valid) for p in refined]
    for choice in choices:
        idx=choice['selected_candidate']
        choice['evaluation_only_error']=refined_errors[idx-1] if idx is not None else None
    return {'scene':record,'current_speed_mps':conversion['current_speed_mps'],
            'candidate_count':len(rows),'passing_count':len(checked),'rejections':report['summary']['rejection_counts'],
            'baselines':{
                'raw_mtr_highest_score':{'candidate':high+1,'error':raw_errors[high],'trajectory_source':'raw_MTR'},
                'refined_highest_score':{'candidate':high+1,'error':refined_errors[high],'trajectory_source':'bounded_refinement'},
                'refined_checked_highest_score':{'candidate':filtered+1 if filtered is not None else None,
                                                'error':refined_errors[filtered] if filtered is not None else None,'trajectory_source':'bounded_refinement'},
                'raw_oracle_minade':{'error':min(raw_errors,key=lambda r:r['ade_m']),'selection_uses_future':True},
                'refined_oracle_minade':{'error':min(refined_errors,key=lambda r:r['ade_m']),'selection_uses_future':True}},
            'diagnostic_choices':choices,
            'source_hashes':{'raw_candidates':sha256(out/'internal_0000.npz'),'checks':sha256(out/'anchored_feasibility.json')},
            'scope':'Diagnostic instruction coverage/self-consistency under the same heuristic used for selection. Not independent semantic accuracy, confirmed doPlan compliance, closed-loop success, or safety.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default='baseline-v1');parser.add_argument('--split',default='development',choices=['development','evaluation']);args=parser.parse_args()
    folder=ROOT/'runs/project-v2'/args.tag
    records=json.loads((folder/f'{args.split}-manifest.json').read_text())
    results=[evaluate_window(record) for record in records]
    by_action={}
    for instruction in INSTRUCTIONS:
        entries=[c for result in results for c in result['diagnostic_choices'] if c['instruction']==instruction]
        chosen=[c for c in entries if c['selected_candidate'] is not None]
        by_action[instruction]={'selected':len(chosen),'windows':len(entries),
                               'coverage_fraction':len(chosen)/len(entries) if entries else None,
                               'selected_ade_m':summarize_optional([c['evaluation_only_error']['ade_m'] for c in chosen])}
    summary={'split':args.split,'windows':len(results),'recordings':len({r['scene']['recording_id'] for r in results}),
             'total_candidates':sum(r['candidate_count'] for r in results),
             'passing_candidates':sum(r['passing_count'] for r in results),
             'by_diagnostic_instruction':by_action,
             'baseline_errors':{name:summarize_optional([r['baselines'][name]['error']['ade_m'] if r['baselines'][name]['error'] else None for r in results])
                                for name in ('raw_mtr_highest_score','refined_highest_score','refined_checked_highest_score','raw_oracle_minade','refined_oracle_minade')},
             'warning':'Unmatched instructions do not have a ground-truth driven future. ADE is descriptive replay error, not language compliance. Always report selection coverage beside selected-only errors.'}
    write_json(folder/f'{args.split}-evaluation.json',{'summary':summary,'windows':results})
    print(json.dumps(summary,indent=2))
    annotations,source=load_release(ROOT/'references/release_annotationsV1.csv')
    v1=inventory(annotations,parse_v1);v2=inventory(annotations,parse_v2)
    runnable=sum(parse_v2(r.instruction).get('runnable_without_external_events',False) for r in annotations if r.instruction)
    write_json(ROOT/'runs/project-v2/language/parser-coverage.json',{'source':source,
        'v1_counts':v1['counts'],'v2_counts':v2['counts'],'v2_without_external_grounding':runnable,
        'v2_actions':v2['parsed_actions'],'v2_unsupported_examples':v2['unsupported_examples'],
        'note':'Parser coverage measures accepted grammar, not correctness on natural language; a manually reviewed test set is required.'})

if __name__=='__main__':main()
