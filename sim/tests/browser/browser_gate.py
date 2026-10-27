import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
"""Audit actual browser journeys, phase order, geometry and continuous motion."""
import json,math,sys,re
from pathlib import Path
from datetime import datetime
root=Path(__file__).parents[1];out=root/'results'
default_logs=(Path(__file__).resolve().parents[3]/'logs')
cfg=json.loads((out/'browser-run-config.json').read_text())
def time(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def angle(a,b):return math.atan2(math.sin(a-b),math.cos(a-b))
def audit(name):
 c=cfg[name];start=time(c['start']);end=time(c['end'])
 logs=Path(c.get('traceRoot',str(default_logs)))
 events=[json.loads(x) for x in (logs/'events.jsonl').read_text().splitlines()]
 rows=[e for e in events if start<=time(e['time'])<=end]
 rows=[e for e in rows if e.get('client_release')=='refactor-v39']
 session=next(e['session_id'] for e in rows if e['type']=='activated')
 rows=[e for e in rows if e.get('session_id')==session]
 terminals=[e for e in rows if e['type'] in ('completed','applied','timed_out','blocked','error','unsupported','cancelled','skipped')]
 # cancel() clears the current row before emitting its stop event. Recover
 # the cancelled action only from its preceding, still-open activation.
 for e in terminals:
  if e['type']=='cancelled' and e.get('action') is None:
   active=next(x for x in reversed(rows) if x['type']=='activated' and time(x['time'])<time(e['time']))
   assert not any(x.get('stage_id')==active['stage_id'] and x['type'] in ('completed','applied','timed_out','skipped') and time(active['time'])<time(x['time'])<time(e['time']) for x in rows)
   e['action']=active['action']
 assert [(e.get('action'),e['type']) for e in terminals]==[tuple(x) for x in c['expected']],(name,[(e.get('action'),e['type']) for e in terminals])
 checks=[];previous=None
 for e in terminals:
  if e['type']!='completed':previous=e;continue
  req=json.loads((logs/'requests'/(e['request_id']+'.json')).read_text());r=req['result']
  installs=[x for x in rows if x['type']=='route_installed' and x.get('stage_id')==e['stage_id']]
  phases=r.get('phases',[r]);assert len(installs)==len(phases),(name,'duplicate or missing phase')
  if previous:assert time(installs[0]['time'])>=time(previous['time']), 'command overtook predecessor'
  previous=e
  expected=e['execution']['expected_finish'];actual=e['state']
  assert math.dist(actual['xy'],expected['xy'])<.4,(name,e['action'],'wrong destination')
  assert abs(angle(actual['heading'],expected['heading']))<.08
  # Completion has an explicit 2 cm integration tolerance. Map node labels
  # switch at shared segment boundaries. Check the actual boundary, rather
  # than requiring two labels on opposite sides of the same centimeter to match.
  boundary_tolerance=0
  if actual.get('node_id')!=expected.get('node_id'):
   proof=r['route'].get('lane_change',{})
   error=math.dist(actual['xy'],expected['xy'])
   assert error<=.02,(name,e['stage_id'],e['action'],error,actual,expected)
   segments=r['route']['segments']
   assert any(a['node_id']==actual['node_id'] and b['node_id']==expected['node_id'] and
    abs(a['end']-r['completion_m'])<.02 and abs(b['start']-r['completion_m'])<.02
    for a,b in zip(segments,segments[1:]))
   if e['action'].startswith('lane_change') or e['action']=='select_lane':
    # A change can span the initial target connector into its next lane.
    # target is the proven endpoint; target_corridor is only the entry section.
    assert actual['node_id']==proof['source_corridor'] and expected['node_id']==proof['target']
   else:
    assert actual['node_id'].startswith('L')
    assert any(m['connector']==expected['node_id'] and (m['action']=='go_straight' or m.get('road_bend')) for m in r['route']['movements'])
   boundary_tolerance=error
  trace=e['journey'];a=e['action'];source=e.get('route_source')
  assert source or a.startswith('reverse'),(name,a,'missing maneuver identity')
  turns=[m for m in trace['observed_movements'] if m['action']!='go_straight' and not m.get('road_bend')]
  assert all(m['action']==a and m['connector']==source for m in turns),(name,a,'unrequested turn',turns)
  if a in ('turn_left','turn_right','u_turn'):
   assert any(m['connector']==source for m in turns),(name,a,'turn never driven')
  if len(phases)>1:
   finishes=e['phases'];assert len(finishes)==len(phases)
   for i,(phase,finish) in enumerate(zip(phases,finishes)):
    assert finish['index']==i
    assert bool(finish['reverse'])==bool(phase['route'].get('reverse'))
    assert math.dist(finish['finish']['xy'],finish['expected_finish']['xy'])<.05
    if i<len(phases)-1:
     assert finish['finish']['speed']==0
     assert math.dist(finish['finish']['xy'],installs[i+1]['state']['xy'])<.001
   assert abs(angle(actual['heading'],trace['origin']['heading']))>2.9
  prep=r['route'].get('preparation')
  if prep:
   assert prep['lane_delta']==1 and prep['action']=='lane_change_right'
   assert prep['end']<r['maneuver_start_m'], 'preparation occurred after the turn'
   assert r['route']['geometry_source']=='prepared_mapped_turn'
  if a.startswith('lane_change'):
   proof=r['route']['lane_change'];assert proof['lane_delta']==(-1 if a.endswith('left') else 1)
  if a=='select_lane':
   proof=r['route']['lane_change'];assert proof['lane_delta']!=0
   assert (proof['lane_delta']<0)==(req['request']['stage']['lane_reference']=='leftmost')
  checks.append(dict(action=a,source=source,phases=len(phases),preparation=prep,
    position_error_m=math.dist(actual['xy'],expected['xy']),finish_node=actual.get('node_id'),
    boundary_node_tolerance_m=boundary_tolerance))
 telemetry=[e for e in rows if e['type']=='telemetry']
 assert telemetry and all(e['position_jumps']==0 and e['layout_shifts']==0 for e in telemetry)
 assert all(e.get('max_heading_step',0)<.2 for e in telemetry),'abrupt heading change'
 assert all(b['moving_seconds']>=a['moving_seconds'] for a,b in zip(telemetry,telemetry[1:]))
 for e in telemetry:
  m=e.get('current_movement')
  if e['phase']=='continuation' and m and m['action']!='go_straight' and not m.get('road_bend'):
   assert m['connector']==terminals[-1].get('route_source'),'unrequested turn after queue completion'
 return dict(session_id=session,checks=checks,telemetry=telemetry,terminals=terminals,rows=rows)
if '--aux' in sys.argv:
 print(json.dumps({name:audit(name)['checks'] for name in ('cancel_late','cancel','timeout')},indent=2))
 sys.exit(0)
reports={name:audit(name) for name in cfg if cfg[name].get('status')!='known_failure'}
main=reports['main'];last=main['telemetry'][-1]
assert len(main['checks'])>=3 and last['moving_seconds']>=30 and last['longest_stall']<1
# A completed turn alone missed the reported bug. Require continued motion
# for at least five seconds with no new instruction and no stopped sample.
for name,r in reports.items():
 right=next(e for e in r['terminals'] if e.get('route_source')=='C70254')
 next_instruction=next(e for e in r['rows'] if e['type']=='activated' and time(e['time'])>time(right['time']))
 assert (time(next_instruction['time'])-time(right['time'])).total_seconds()>=5,(name,'continuation requires a fresh command')
 tail=[e for e in r['telemetry'] if 0<(time(e['time'])-time(right['time'])).total_seconds()<10]
 assert tail and all(e['state']['speed']>.1 for e in tail),(name,'stopped after right turn')
 assert any(e['state'].get('node_id') in ('C69782','L67695') for e in tail),(name,'natural continuation not observed')
wall=(time(main['terminals'][-1]['time'])-time(cfg['main']['start'])).total_seconds()
assert wall<=60,('multi-action browser run exceeded one minute',wall)
assert wall-last['moving_seconds']<5,('unexpected stopped time',wall,last['moving_seconds'])
samples=json.loads((out/'browser-samples.json').read_text())
assert all(s['activeVisible'] for s in samples),'active instruction scrolled out of view'
assert all(s['englishOnly'] for s in samples),'non-English interface text'
assert max(s['queueScroll'] for s in samples)>0,'queue following was not exercised'
# DOMRect carries y, top and bottom in viewport coordinates. Clicking Pause
# scrolls the browser by 59 px; normalize every vertical field consistently.
assert len({json.dumps({**s['canvas'],**{k:s['canvas'][k]+s.get('scrollTop',0) for k in ('y','top','bottom')}},sort_keys=True) for s in samples})==1,'canvas document layout changed'
assert not json.loads((out/'browser-errors.json').read_text())
final_moving=float(re.search(r'Moving time ([\d.]+)',samples[-1]['monitor']).group(1))
wall_total=(time(cfg['main']['end'])-time(cfg['main']['start'])).total_seconds()
assert final_moving>=30 and wall_total-final_moving<12,(wall_total,final_moving)
report=dict(passed=True,scene=1,target_speed_kmh=cfg["main"].get("target_speed_kmh",20),reverse_limit_kmh=5.4,
 session_id=main['session_id'],
 recovery_turn_limit_kmh=10.8,moving_seconds=final_moving,wall_seconds=wall_total,
 telemetry_moving_seconds=last['moving_seconds'],
 distance_m=float(re.search(r'Distance ([\d.]+)',samples[-1]['monitor']).group(1)),
 longest_stall=last['longest_stall'],position_jumps=last['position_jumps'],layout_shifts=last['layout_shifts'],
 commands={name:r['checks'] for name,r in reports.items()},
 queue_follow_verified=all(s.get('activeVisible',True) for s in samples),
 console_errors=0)
(out/'browser-gate.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
