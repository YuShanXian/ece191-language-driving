"""Compare all 35 original human road choices, retaining provenance and caveats."""
import sys,json,math,hashlib
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).parents[2]))
from engine.geometry import ROOT,heading,angle_diff
from engine.scene import get_scene
from engine.planner import plan,stage

out=Path(__file__).parents[1]/'results'
base=ROOT/'runs/project-v3'
sources=['language-choice-v1/report-reviewed/human-review/round-2/reviews.json',
 'instruction-priority-v6/human-review/reviews.json',
 'instruction-priority-v7/human-review/targets.json',
 'human-target-v8/human-targets-snapshot.json',
 'automatic-road-v9/human-review/reviews.json']
evidence={}
for rel in sources:
 p=base/rel
 evidence[rel]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'data':json.loads(p.read_text())}
(out/'original-human-reviews.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
targets=evidence[sources[2]]['data']['reviews']
actions=['go_straight','turn_left','turn_right','lane_change_left','lane_change_right']
rows=[]
for n in range(1,8):
 s=get_scene(n);state={'xy':[0,0],'heading':0,'speed':0,'target_speed_mps':20/3.6}
 for i,a in enumerate(actions):
  human=next(x for x in targets if x['scene']==n and x['command']==i)
  r=plan({'scene':n,'state':state,'stage':stage(a)})
  if n in (1,6) and a == 'lane_change_left':
   assert r['status']=='waiting', 'Do not create a left-then-right detour into the same exit'
  route=r.get('route') or {};segments=route.get('segments',[])
  descriptions=[]
  for key in human['road_ids']:
   if key not in s.nodes:continue
   move=s.topology.by_connector.get(key)
   descriptions.append({'road':key,'action':move.action if move else 'lane_or_unaligned_connector',
     'target':move.target if move else None,'turn_degrees':math.degrees(angle_diff(heading(s.points[key],True),heading(s.points[key])))})
  match=[k for k in human['road_ids'] if k in [x['node_id'] for x in segments]]
  row={'scene':n,'command':i,'action':a,'human_targets':descriptions,'status':r['status'],
   'route_source':r.get('route_source'),'begin':r.get('maneuver_start_m'),
   'completion':r.get('completion_m'),'human_road_overlap':match,
   'movements':route.get('movements',[]),'first_nodes':[x['node_id'] for x in segments[:8]],'reason':r.get('reason')}
  rows.append(row)
  print(n,a,r['status'],r.get('route_source'),'begin',round(r.get('maneuver_start_m',0),1),'human',[(x['road'],x['action']) for x in descriptions], 'overlap',match,flush=True)
(out/'human-review-comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
print('SUMMARY',dict(Counter(x['status'] for x in rows)),flush=True)
