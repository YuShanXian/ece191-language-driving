import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
"""Audit the actual browser trace from activation, including waiting and tail."""
import json,math,sys
from pathlib import Path
from datetime import datetime
out=Path(__file__).parents[1]/'results'
config=json.loads((out/'browser-run-config.json').read_text())
log=(Path(__file__).resolve().parents[3]/'logs/events.jsonl')
events=[json.loads(l) for l in log.read_text(encoding='utf-8').splitlines() if l.strip()]
start=datetime.fromisoformat(config['start_utc'].replace('Z','+00:00'))
candidates=[x for x in events if x.get('type')=='activated' and x.get('action')=='go_straight' and
 datetime.fromisoformat(x['time'].replace('Z','+00:00'))>=start]
session=candidates[0]['session_id']
events=[x for x in events if x.get('session_id')==session]
completed=[x for x in events if x['type']=='completed']
failures=[]
if [x['action'] for x in completed]!=config['expected_actions']:failures.append('Not all expected maneuvers completed in order')
bad=[x for x in events if x['type'] in ['timed_out','error','blocked','unsupported','cancelled']]
if bad:failures.append('Unexpected failed or cancelled command')
checks=[]
for e in completed:
 trace=e['journey'];a=e['action'];execution=e['execution'];actual=e['state']
 turns=[m for m in trace['observed_movements'] if m['action']!='go_straight' and not m.get('road_bend')]
 if any(m['action']!=a or m['connector']!=e.get('route_source') for m in turns):failures.append(f'Unrequested turn in complete journey: {a}')
 if a in ['turn_left','turn_right','u_turn'] and not any(m['connector']==e['route_source'] for m in turns):
  failures.append(f'Requested turn not actually observed: {a}')
 expected=execution['expected_finish'];error=math.dist(actual['xy'],expected['xy'])
 if error>.4:failures.append(f'Incorrect completion position: {a}, {error}')
 if a.startswith('lane_change'):
  begin=trace['origin'];h=begin['heading'];delta=[actual['xy'][j]-begin['xy'][j] for j in range(2)]
  lateral=-math.sin(h)*delta[0]+math.cos(h)*delta[1]
  if a=='lane_change_left' and lateral<1:failures.append('Left lane change did not move left')
  if a=='lane_change_right' and lateral>-1:failures.append('Right lane change did not move right')
 else:lateral=None
 checks.append({'stage':e['stage_id'],'action':a,'source':e.get('route_source'),
   'position_error_m':error,'lateral_m':lateral,'journey_samples':len(trace['samples']),
   'observed_movements':trace['observed_movements']})
if completed:
 first=completed[0]
 if first['route_source']!='J_L63477_L67723':failures.append('First straight chose a different exit')
 if any(abs(x['heading'])>math.radians(15) for x in first['journey']['samples']):failures.append('First straight made an unexpected turn')
telemetry=[x for x in events if x['type']=='telemetry']
last=telemetry[-1] if telemetry else {}
moving=last.get('moving_seconds',0)
if moving<300:failures.append(f'Less than 300 seconds actual movement: {moving}')
if last.get('position_jumps',1)!=0:failures.append('Position continuity failed')
if last.get('layout_shifts',1)!=0:failures.append('Layout moved during run')
if last.get('longest_stall',100)>1:failures.append('Unexpected stall')
wall=(datetime.fromisoformat(last['time'].replace('Z','+00:00'))-datetime.fromisoformat(candidates[0]['time'].replace('Z','+00:00'))).total_seconds() if telemetry else 0
if completed:
 wall_to_finish=(datetime.fromisoformat(completed[-1]['time'].replace('Z','+00:00'))-datetime.fromisoformat(candidates[0]['time'].replace('Z','+00:00'))).total_seconds()
 if wall_to_finish-moving>3:failures.append('Stopped time or wall-clock mismatch during continuous run')
else:wall_to_finish=0
report={'passed':not failures,'session_id':session,'scene':1,'moving_seconds':moving,'wall_seconds_to_final_command':wall_to_finish,
 'target_speed_kmh':20,'reverse_speed_kmh':5.4,'distance_m':last.get('distance_m'),
 'completed':len(completed),'failures':failures,'checks':checks,'telemetry_samples':len(telemetry),
 'position_jumps':last.get('position_jumps'),'layout_shifts':last.get('layout_shifts'),'longest_stall':last.get('longest_stall')}
(out/'browser-gate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False,indent=2))
sys.exit(bool(failures))
