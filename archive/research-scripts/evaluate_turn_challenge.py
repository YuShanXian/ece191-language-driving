"""Compare internal64 versus original final5 on every fixed new-recording anchor."""
import json
from collections import Counter
import numpy as np
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.planner import OfflinePlanner
from mtr_project.stages import Observation
from language_selector import action_matches


def main():
    base=ROOT/'runs/project-v2/turn-challenge-v1';plan_path=base/'window-plan.json';plan=json.loads(plan_path.read_text())
    spec_path=ROOT/'config/turn-challenge-v1-evaluation.json';spec=json.loads(spec_path.read_text())
    manifest=json.loads((base/'manifest.json').read_text())
    if manifest!=plan['windows']:raise ValueError('Challenge is incomplete or changed')
    output=base/'evaluation.json'
    if output.exists():raise FileExistsError('Preserve prior challenge evaluation')
    sources={str(p.relative_to(ROOT)):sha256(p) for p in [plan_path,spec_path,base/'manifest.json']}
    for mapping in [plan['source_sha256'],plan['implementation_sha256']]:
        for name,digest in mapping.items():
            if sha256(ROOT/name)!=digest:raise ValueError('Challenge source changed: '+name)
    results=[]
    for row in manifest:
        folder=ROOT/'runs'/row['run'];sample=ROOT/'samples'/row['sample'];conv_path=sample/'conversion.json';conv=json.loads(conv_path.read_text())
        screen_path=folder/'anchored_feasibility.json';screen=json.loads(screen_path.read_text());candidates=screen['candidates']
        raw_path=folder/'internal_0000.npz';cached=np.load(raw_path)
        final5=[int(x)+1 for x in cached['selected_indices']]
        if len(candidates)!=64 or len(final5)!=5 or len(set(final5))!=5 or not set(final5)<=set(range(1,65)):raise ValueError('Unexpected MTR candidate cardinality')
        if conv['current_timestamp_us']!=row['timestamp_us']:raise ValueError('Wrong converted anchor')
        choices=[];observation=Observation(row['timestamp_us']/1e6,0,0,conv['current_speed_mps'])
        for instruction in spec['primary_instructions']:
            all_choice=OfflinePlanner(instruction).step(observation,candidates)
            final_choice=OfflinePlanner(instruction).step(observation,[c for c in candidates if c['candidate'] in final5])
            action=all_choice['stage']['action'];matching=[c for c in candidates if action_matches(c,action,conv['current_speed_mps'])]
            choices.append({'instruction':instruction,'action':action,'all64':all_choice,'final5':final_choice,
                            'matching_action_before_other_checks':[c['candidate'] for c in matching],
                            'rejections_of_action_matching_candidates':dict(Counter(reason for c in matching for reason in c['rejected_by']))})
        results.append({'window':row,'speed_mps':conv['current_speed_mps'],'passing_candidates':sum(c['passes_current_checks'] for c in candidates),
                        'passing_final5':sum(c['passes_current_checks'] for c in candidates if c['candidate'] in final5),
                        'original_final5':final5,'rejections':screen['summary']['rejection_counts'],'choices':choices})
        for path in [conv_path,raw_path,screen_path,folder/'refined_v2_candidates.npz',sample/conv['scenario']]:sources[str(path.relative_to(ROOT))]=sha256(path)
    summary={}
    for group in spec['report_groups']:
        cohort=[r for r in results if group=='all_unique_anchors' or any(s['kind']==('fixed_fraction' if group=='fixed_fraction_anchors' else 'official_tag') for s in r['window']['sampling'])]
        summary[group]={'windows':len(cohort),'candidate_count':64*len(cohort),'passing_candidates':sum(r['passing_candidates'] for r in cohort),
                        'by_instruction':{text:{pool:sum(c[pool]['candidate'] is not None for r in cohort for c in r['choices'] if c['instruction']==text) for pool in ['all64','final5']} for text in spec['primary_instructions']}}
    result={'status':'completed_fixed_turn_challenge','specification':spec,'summary':summary,'windows':results,'source_sha256':sources,
            'implementation_sha256':{name:sha256(ROOT/name) for name in ['scripts/evaluate_turn_challenge.py','scripts/mtr_project/planner.py','scripts/mtr_project/language.py','scripts/mtr_project/stages.py','scripts/language_selector.py']},
            'scope':spec['scope'],'alignment_claim':'New annotation frame-to-DB alignment not established; annotation used for recording context only.'}
    write_json(output,result);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
