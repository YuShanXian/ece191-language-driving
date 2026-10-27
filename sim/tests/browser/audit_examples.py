import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
"""Check submitted language, semantic order, actual destinations and complete journeys."""
import json,math,re
from pathlib import Path
root=Path(__file__).parents[1];out=root/'results'
cfg=json.loads((out/'browser-run-config.json').read_text())
samples=json.loads((out/'browser-samples.json').read_text())
expected={1:['keep_lane'],2:['go_straight'],3:['turn_left'],4:['turn_right'],
 5:['go_straight','lane_change_right'],6:['go_straight','lane_change_right','lane_change_left'],
 7:['keep_lane'],8:['keep_lane'],9:['reverse'],10:['keep_lane','reverse']}
distances={1:[15],7:[15],8:[20],9:[5],10:[10,5]}
angle=lambda a,b:math.atan2(math.sin(a-b),math.cos(a-b))
reports=[]
for name,c in cfg.items():
 if not c.get('end') or c.get('status')=='known_failure':continue
 logs=Path(c['traceRoot']);all_events=[json.loads(x) for x in (logs/'events.jsonl').read_text().splitlines()]
 events=[e for e in all_events if c['start']<=e['time']<=c['end']]
 parsed=next(e for e in events if e['type']=='parse' and e['instruction']==c['instruction'])
 plan=parsed['result'];assert plan['status']=='parsed' and not plan.get('unresolved_text'),(name,plan)
 stages=plan['stages'];actions=[s['action'] for s in stages if s['action'] not in ('stop','hold_stopped')]
 number=c['number'];want=expected[number]
 if number in (7,8) and actions[0]=='set_speed':want=['set_speed',*want]
 # Both distance-follow spellings are accepted, but never omit the distance.
 norm=lambda xs:['keep_lane' if x=='go_straight' and i<len(want) and want[i]=='keep_lane' else x for i,x in enumerate(xs)]
 assert norm(actions)==want,(name,actions,want)
 if number in distances:
  actual=[s['travel_distance_m'] for s in stages if s.get('travel_distance_m') is not None]
  assert actual==distances[number],(name,'distance parsed incorrectly',actual)
 if number in (7,8):
  speed=10 if number==7 else 20
  speeds=[s['target_speed_mps'] for s in stages if s.get('target_speed_mps') is not None]
  assert speeds and all(abs(v*3.6-speed)<.01 for v in speeds),(name,'wrong speed parameter',speeds)
 session=next(e['session_id'] for e in events if e['type']=='activated')
 rows=[e for e in events if e.get('session_id')==session]
 terminals=[e for e in rows if e['type'] in ('completed','applied','timed_out','blocked','error','unsupported','cancelled','skipped')]
 assert [e['action'] for e in terminals]==[s['action'] for s in stages],(name,'missing or extra commands')
 assert all(e['type'] in ('completed','applied') for e in terminals),(name,'failed command')
 c['expected']=[[e['action'],e['type']] for e in terminals]
 checks=[]
 for e in terminals:
  if e['type']!='completed':continue
  if not e.get('request_id'):
   assert e['action'] in ('stop','hold_stopped') and e['state']['speed']<.02,(name,'unverified local completion')
   continue
  req=json.loads((logs/'requests'/(e['request_id']+'.json')).read_text());r=req['result']
  actual=e['state'];finish=e['execution']['expected_finish']
  assert math.dist(actual['xy'],finish['xy'])<.4 and abs(angle(actual['heading'],finish['heading']))<.08
  turns=[m for m in e['journey']['observed_movements'] if m['action']!='go_straight' and not m.get('road_bend')]
  assert all(m['action']==e['action'] and m['connector']==e.get('route_source') for m in turns),(name,'unrequested turn',turns)
  if e['action'] in ('turn_left','turn_right'):assert turns,(name,'turn never driven')
  if e['action'].startswith('lane_change'):
   assert r['route']['lane_change']['lane_delta']==(-1 if e['action'].endswith('left') else 1)
  movement=e['execution']['distance'];wanted=req['request']['stage'].get('travel_distance_m')
  if wanted is not None:assert abs(movement-wanted)<.4,(name,'distance not driven',movement,wanted)
  activation=next(x for x in rows if x['type']=='activated' and x['stage_id']==e['stage_id'])
  prior=[x for x in terminals if x['stage_id']!=e['stage_id'] and x['time']<e['time']]
  if prior:assert activation['time']>=prior[-1]['time'],(name,'out of order')
  checks.append(dict(action=e['action'],source=e.get('route_source'),distance_m=movement,position_error_m=math.dist(actual['xy'],finish['xy']),destination=actual.get('node_id')))
 telemetry=[e for e in rows if e['type']=='telemetry']
 if number in (7,8):
  cap=(10 if number==7 else 20)/3.6
  installations=[e for e in rows if e['type']=='route_installed']
  assert installations and all(abs(e['state']['target_speed_mps']-cap)<.01 for e in installations)
  assert all(e['state']['speed']<=cap+.02 for e in telemetry),(name,'exceeded requested speed')
 assert all(e['position_jumps']==0 and e['layout_shifts']==0 and e.get('max_heading_step',0)<.2 for e in telemetry)
 final=next(s for s in reversed(samples) if s['name']==name)
 assert final['summary'].startswith('Pipeline finished') and 'Speed 0.0 km/h' in final['monitor'],(name,'not completely stopped',final)
 assert all(s['activeVisible'] and s['englishOnly'] for s in samples if s['name']==name)
 reports.append(dict(case=name,instruction=c['instruction'],model=parsed['model'],parse_seconds=parsed['elapsed_ms']/1000,monitor=final['monitor'],checks=checks,passed=True))
(out/'browser-run-config.json').write_text(json.dumps(cfg,indent=2))
(out/'example-audit.json').write_text(json.dumps(reports,indent=2))
print(json.dumps(reports,indent=2))
