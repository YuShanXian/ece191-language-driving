exec(open('historical-project/scripts/audit_history_execute_v17.py').read().split('records=json.loads')[0])
rows=json.loads((out/'full-replay.json').read_text());inventory={x['path']:x for x in json.loads((out/'inventory.json').read_text())}
for row in rows:
 if row['status'] in ('completed_offline','live_control'):continue
 x=inventory[row['path']];key=hashlib.sha256(x['instruction'].encode()).hexdigest()[:16];plan=json.loads((out/'fresh-parses'/(key+'.json')).read_text())['parsed'];e=execute(x['scene'] or 7,plan,x['state'],'free');(out/'executions'/row['execution']).write_text(json.dumps(e));row.update(status=e['status'],reason=e.get('reason') or ' / '.join(s.get('reason','') for s in e.get('stages',[])),lane_changes=[c for s in e.get('stages',[]) for c in s.get('preparatory_lane_changes',[])])
 if e['status']=='completed_offline':
  pp=np.asarray(e['points']);row['start_error_m']=float(np.linalg.norm(pp[0]-x['state']['xy']));row['max_step_m']=float(np.linalg.norm(np.diff(pp,axis=0),axis=1).max());assert row['start_error_m']<.1
 print(x['instruction'],row['status'],row['reason'],flush=True)
(out/'full-replay.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
