exec(open('historical-project/scripts/direct_worker_v19.py').read().split('for line in sys.stdin:')[0])
from pathlib import Path
rows=[json.loads(l) for l in open('historical-project/runs/project-v3/recording-demo-v1/command-history.jsonl')]
r=next(r for r in rows if r.get('status')=='received' and r['id']=='ui-1792576009464')
from execute_language_plan_v3 import execute as finite
st=dict(action='lane_change_left',source_clause='left',trigger='now',trigger_text='',trigger_value=None,target_text='',lane_reference='none',lane_number=None,completion_text='',constraints=[],travel_distance_m=None,stop_at_end=False,target_speed_mps=15)
e=finite(7,{'status':'parsed','stages':[st],'unresolved_text':[]},r['state'],'free');print('original',e['points'][:8],e['speed_mps'][:8],e['stages'])
from route_speed_v18 import sample
p,v=sample(e['points'],15,r['state']['speed']);print('retimed',p[:6],v[:6],'total',len(p))
