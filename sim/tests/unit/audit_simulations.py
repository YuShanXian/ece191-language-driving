import json
from fixtures import ROOT,load_scene
from reverse_audit import audit_reverse
reports=[]
for file in sorted((ROOT/'results').rglob('*.json')):
    data=json.loads(file.read_text())
    if not isinstance(data,dict) or not data.get('motion_samples'):continue
    scene=load_scene(data['spec'].get('scene',1))
    # Audit installed motion even when a later click cancels it. A bad partial
    # reverse cannot disappear behind a cancelled result in random exploration.
    for event in data['events']:
        if event['type']!='route_installed' or not event.get('action','').startswith('reverse'):continue
        request=next(r for r in data['requests'] if str(r['id'])==event['request_id'])
        route=request['response']['route'];state=request['request']['state']
        path=audit_reverse(scene,state,route)
        end=next((e for e in data['events'] if e['sim_time']>=event['sim_time'] and e.get('stage_id')==event['stage_id'] and e['type'] in ('completed','cancelled','timed_out','error')),None)
        actual=[p for p in data['motion_samples'] if p.get('stage_id')==event['stage_id'] and p.get('status')=='executing' and p['reverse'] and p['time']>=event['sim_time'] and (end is None or p['time']<=end['sim_time'])]
        if end and end['type']=='completed':assert actual,'no executed reverse samples'
        physical=audit_reverse(scene,state,route,actual=actual) if actual else dict(samples=0,max_lateral_error_m=0)
        reports.append(dict(case=str(file.relative_to(ROOT/'results')),stage=event['stage_id'],outcome=end['type'] if end else 'incomplete',planned=path,executed=physical))
(ROOT/'results/simulation-reverse-audit.json').write_text(json.dumps(reports,indent=2))
print(json.dumps(dict(installed_reverses_audited=len(reports),completed=sum(r['outcome']=='completed' for r in reports),cancelled=sum(r['outcome']=='cancelled' for r in reports),actual_samples=sum(r['executed']['samples'] for r in reports),worst_lateral_error_m=max(r['executed']['max_lateral_error_m'] for r in reports))))
