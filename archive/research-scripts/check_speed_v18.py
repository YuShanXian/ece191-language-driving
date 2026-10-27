exec(open('historical-project/scripts/audit_history_execute_v17.py').read().split('records=json.loads')[0])
from route_speed_v18 import sample
for target in [20/3.6,30/3.6]:
 pp,v=sample([[0,0],[100,0]],target,0,True);assert max(v)>.98*target;assert max(v)<=target+.02;assert v[-1]==0;assert np.linalg.norm(pp[-1]-[100,0])<1e-6
print('Straight acceleration / target speed / exact stopping: passed',flush=True)
items=json.loads((out/'inventory.json').read_text());records=[x for x in items if x['state'] is not None][-20:];rows=[]
for x in records:
 key=hashlib.sha256(x['instruction'].encode()).hexdigest()[:16];plan=json.loads((out/'fresh-parses'/(key+'.json')).read_text())['parsed'];state={**x['state'],'target_speed_mps':20/3.6};e=execute(x['scene'] or 7,plan,state,'free');rows.append({'input':x['instruction'],'status':e['status'],'reason':e.get('reason') or ' / '.join(s.get('reason','') for s in e.get('stages',[]))});print(x['instruction'],e['status'],flush=True)
(r/'runs/project-v3/direct-commands-v18/navigation-regression.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
