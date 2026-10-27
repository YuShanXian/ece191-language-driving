exec(open('historical-project/scripts/direct_worker_v19.py').read().split('for line in sys.stdin:')[0])
from pathlib import Path
rows=[json.loads(l) for l in open('historical-project/runs/project-v3/recording-demo-v1/command-history.jsonl')];rows=[r for r in rows if r.get('status')=='received' and r.get('source')=='direct button'][-35:];out=[]
for r in rows:
 st=dict(action=r['instruction'].replace(' ','_'),source_clause=r['instruction'],trigger='now',trigger_text='',trigger_value=None,target_text='',lane_reference='none',lane_number=None,completion_text='',constraints=[],travel_distance_m=None,stop_at_end=False,target_speed_mps=None)
 if st['action'] not in ('turn_right','turn_left','go_straight','lane_change_left','lane_change_right'):continue
 e=execute(7,{'status':'parsed','stages':[st],'unresolved_text':[]},r['state'],'free');p=np.asarray(e['points']);v=e['speed_mps'];row={'id':r['id'],'action':st['action'],'status':e['status'],'speed_before':r['state']['speed'],'speed_next':v[1] if len(v)>1 else None,'reason':[x.get('reason') for x in e['stages']],'lane_changes':[x.get('preparatory_lane_changes') for x in e['stages']]};print(row,flush=True);out.append(row)
 if len(p)>1:assert np.linalg.norm(p[0]-r['state']['xy'])<.01;assert np.isfinite(p).all()
folder=Path('historical-project/runs/project-v3/navigation-fix-v20');folder.mkdir(exist_ok=True);(folder/'replay.json').write_text(json.dumps(out,indent=2))
