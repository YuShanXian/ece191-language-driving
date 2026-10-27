"""Evaluate the fixed cached-controller filter on every declared active action pair."""
import json
from collections import defaultdict
from functools import lru_cache
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.tracking_selection import apply_tracking_filter,REQUIRED_CASES


@lru_cache(maxsize=None)
def digest(path):return sha256(path)


def main():
    specification=ROOT/'config/tracking-selection-v1.json';spec=json.loads(specification.read_text())
    if {tuple(x) for x in spec['required_cases']}!=REQUIRED_CASES:raise ValueError('Configured settings differ from implemented rule')
    parent_path=ROOT/spec['source_proposals'];tracking_path=ROOT/spec['source_tracking']
    parent=json.loads(parent_path.read_text());tracking=json.loads(tracking_path.read_text())
    verified_path=tracking_path.with_name('verification.json');verified=json.loads(verified_path.read_text())
    if verified['experiment_sha256']!=digest(tracking_path) or verified['rollouts_rechecked']!=54:raise ValueError('Tracking experiment is not fully verified')
    for mapping in [parent['source_sha256'],parent['implementation_sha256'],tracking['source_sha256'],tracking['implementation_sha256']]:
        for name,expected in mapping.items():
            if digest(ROOT/name)!=expected:raise ValueError('Source changed: '+name)
    result_path=ROOT/'runs/project-v2'/spec['output_tag']/'evaluation.json'
    if result_path.exists():raise FileExistsError('Preserve prior selection comparison')
    sources={str(p.relative_to(ROOT)):digest(p) for p in [specification,parent_path,tracking_path,verified_path]};results=[];skipped=[]
    for window in parent['windows']:
        if not window['selections']:
            skipped.append({'window':window['key'],'source_task':window['source_task'],'reason':'No active declared action; never reopen observed completion'})
            continue
        folder=ROOT/'runs'/window['run'];screen_path=folder/'anchored_feasibility.json';screen=json.loads(screen_path.read_text())
        for name,expected in window['output_sha256'].items():
            path=folder/name
            if digest(path)!=expected:raise ValueError('Proposal output changed')
            sources[str(path.relative_to(ROOT))]=expected
        conv_path=ROOT/'samples'/screen['summary']['sample']/'conversion.json';conv=json.loads(conv_path.read_text());sources[str(conv_path.relative_to(ROOT))]=digest(conv_path)
        rows=[r for r in tracking['results'] if r['window']==window['key']]
        audit={'by_candidate':{str(c):{'rollouts':[r for r in rows if r['candidate']==c]} for c in {r['candidate'] for r in rows}}}
        for action,choice in window['selections'].items():
            stage=window['source_task']['stage'] if window['source_task'] is not None else {'state':'active','action':action}
            if stage['state']!='active' or stage['action']!=action:raise ValueError('Declared action differs from measured task state')
            original={'status':'selected_conditionally' if choice['candidate'] is not None else 'no_matching_candidate',
                      'candidate':choice['candidate'],'matching_candidates':choice['matching_candidates'],'stage':stage}
            filtered=apply_tracking_filter(original,screen['candidates'],audit,conv['current_speed_mps'])
            if filtered['status']=='missing_tracking_audit':raise ValueError('Declared comparison population has missing tracking evidence')
            results.append({'window':window['key'],'run':window['run'],'group':window['group'],'action':action,'original':original,'filtered':filtered})
    counts={'active_action_window_pairs':len(results),'original_proposals':sum(r['original']['candidate'] is not None for r in results),
            'filtered_proposals':sum(r['filtered']['candidate'] is not None for r in results),
            'replaced':sum(r['filtered']['candidate'] is not None and r['filtered']['candidate']!=r['original']['candidate'] for r in results),
            'removed':sum(r['original']['candidate'] is not None and r['filtered']['candidate'] is None for r in results),'completed_windows_skipped':len(skipped)}
    output={'status':'completed_declared_cached_tracking_selection','specification':spec,'counts':counts,'results':results,'skipped':skipped,'source_sha256':sources,
            'implementation_sha256':{name:digest(ROOT/name) for name in ['scripts/evaluate_tracking_selection.py','scripts/mtr_project/tracking_selection.py','scripts/language_selector.py']},'historical_results_changed':False}
    write_json(result_path,output)
    print(json.dumps({'counts':counts,'changed_or_retained_proposals':[{'window':r['window'],'action':r['action'],'before':r['original']['candidate'],'after':r['filtered']['candidate']} for r in results if r['original']['candidate'] is not None]},indent=2))


if __name__=='__main__':main()
