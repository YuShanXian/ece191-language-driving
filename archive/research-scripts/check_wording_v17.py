exec(open('historical-project/scripts/audit_history_execute_v17.py').read().split('records=json.loads')[0])
inputs=['Back up a little.','Back the car up a little.','Turn around and head back.']
inventory=json.loads((out/'inventory.json').read_text());state=next(x['state'] for x in reversed(inventory) if x['instruction']=='turn right' and x['state'])
results=[]
for text in inputs:
 key=hashlib.sha256(text.encode()).hexdigest()[:16];plan=json.loads((out/'fresh-parses'/(key+'.json')).read_text())['parsed'];e=execute(7,plan,state,'free');row={'input':text,'status':e['status'],'stages':e.get('stages',[])};results.append(row);print(text,e['status'],flush=True)
 if text.startswith('Back'):assert e['status']=='completed_offline';assert abs(e['stages'][0]['traveled_distance_m']-2)<.01
(out/'wording-checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
