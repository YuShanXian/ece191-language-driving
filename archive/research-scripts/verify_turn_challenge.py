"""Verify full challenge membership, source fingerprints and both-pool choices."""
import json,sqlite3
from collections import Counter
import numpy as np
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.turn_windows import choose_windows
from language_selector import action_matches


def main():
    base=ROOT/'runs/project-v2/turn-challenge-v1';path=base/'evaluation.json';evaluation=json.loads(path.read_text())
    plan=json.loads((base/'window-plan.json').read_text());registration=json.loads((ROOT/'config/turn-challenge-v1.json').read_text())
    checked={}
    for source in [evaluation,plan]:
        for mapping in [source['source_sha256'],source['implementation_sha256']]:
            for name,expected in mapping.items():
                if name not in checked:checked[name]=sha256(ROOT/name)
                if checked[name]!=expected:raise ValueError('Changed dependency: '+name)
    if [r['window'] for r in evaluation['windows']]!=plan['windows']:raise ValueError('Evaluated window population differs')
    for item,record in zip(registration['selected'],plan['records']):
        db=ROOT/'data/nuplan/db'/(item['clip']+'.db')
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
            timestamps=[r[0] for r in conn.execute('SELECT timestamp FROM lidar_pc ORDER BY timestamp')]
            tags={name:[r[0] for r in conn.execute('SELECT DISTINCT p.timestamp FROM scenario_tag s JOIN lidar_pc p ON s.lidar_pc_record_id=p.record_id WHERE s.type=? ORDER BY p.timestamp',(name,))] for name in plan['official_tag_amendment']['types']}
        anchors,missing=choose_windows(timestamps,tags,registration['fractions'])
        saved=[{k:r[k] for k in ['timestamp_us','seconds_after_first_lidar','sampling']} for r in plan['windows'] if r['clip']==item['clip']]
        if anchors!=saved or missing!=record['unavailable']:raise ValueError('Registered metadata anchors do not reproduce')
    for result in evaluation['windows']:
        folder=ROOT/'runs'/result['window']['run'];screen=json.loads((folder/'anchored_feasibility.json').read_text());candidates=screen['candidates']
        cached=np.load(folder/'internal_0000.npz');final5=[int(i)+1 for i in cached['selected_indices']]
        if final5!=result['original_final5'] or len(candidates)!=64:raise ValueError('Pool identity mismatch')
        if sum(r['passes_current_checks'] for r in candidates)!=result['passing_candidates']:raise ValueError('Passing total mismatch')
        if sum(r['passes_current_checks'] for r in candidates if r['candidate'] in final5)!=result['passing_final5']:raise ValueError('Final-five passing total mismatch')
        if result['rejections']!=screen['summary']['rejection_counts']:raise ValueError('Rejection summary mismatch')
        for choice in result['choices']:
            matching=[r for r in candidates if action_matches(r,choice['action'],result['speed_mps'])]
            if [r['candidate'] for r in matching]!=choice['matching_action_before_other_checks']:raise ValueError('Action-only coverage mismatch')
            if dict(Counter(reason for r in matching for reason in r['rejected_by']))!=choice['rejections_of_action_matching_candidates']:raise ValueError('Action rejection summary mismatch')
            for name in ['all64','final5']:
                eligible=[r for r in matching if r['passes_current_checks'] and (name=='all64' or r['candidate'] in final5)]
                chosen=max(eligible,key=lambda r:(r['score'],-r['candidate']),default=None)
                if choice[name]['candidate']!=(chosen['candidate'] if chosen else None):raise ValueError('Ranking mismatch')
                if choice[name]['matching_candidates']!=[r['candidate'] for r in eligible]:raise ValueError('Eligible pool mismatch')
    for group,saved in evaluation['summary'].items():
        cohort=[r for r in evaluation['windows'] if group=='all_unique_anchors' or any(s['kind']==('fixed_fraction' if group=='fixed_fraction_anchors' else 'official_tag') for s in r['window']['sampling'])]
        expected={'windows':len(cohort),'candidate_count':64*len(cohort),'passing_candidates':sum(r['passing_candidates'] for r in cohort),
                  'by_instruction':{text:{pool:sum(c[pool]['candidate'] is not None for r in cohort for c in r['choices'] if c['instruction']==text) for pool in ['all64','final5']} for text in evaluation['specification']['primary_instructions']}}
        if saved!=expected:raise ValueError('Cohort summary mismatch')
    receipt={'status':'passed_declared_turn_challenge_checks','evaluation_sha256':sha256(path),'windows':len(evaluation['windows']),
             'recordings':len(plan['records']),'hashed_dependencies':len(checked),'verifier_sha256':sha256(__file__),
             'scope':'Reconstructed metadata population and score ranking, hashed inputs and outputs. Semantic action predicate shared with baseline; no independent driving truth.'}
    write_json(base/'verification.json',receipt);print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
