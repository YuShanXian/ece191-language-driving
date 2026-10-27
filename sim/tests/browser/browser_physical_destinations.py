import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
"""Use actual browser poses and raw map baselines, not success labels alone."""
import sys,json,pickle,math
from pathlib import Path
from shapely.geometry import Point
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parent))
from engine.geometry import tangent,angle_diff,footprint
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'unit'))
from reverse_audit import audit_reverse
from fixtures import load_scene
s=load_scene(1)
cfg=json.loads((root/'results/browser-run-config.json').read_text())
checks=[]
for name,c in cfg.items():
 if c.get('status')=='known_failure':continue
 s=load_scene(c.get("scene",1))
 trace=c.get('traceRoot',str(Path(__file__).resolve().parents[3]/'logs')).replace('\\','/')
 logs=Path(trace) if not (len(trace)>1 and trace[1]==':' and sys.platform!='win32') else Path('/mnt/'+trace[0].lower()+trace[2:])
 events=[json.loads(x) for x in (logs/'events.jsonl').read_text().splitlines()]
 for e in events:
  if not c['start']<=e['time']<=c['end'] or e['type']!='completed':continue
  action=e['action']
  req=json.loads((logs/'requests'/(e['request_id']+'.json')).read_text())
  r=req['result'];actual=e['state'];point=Point(actual['xy'])
  if action.startswith('reverse'):
   check=audit_reverse(s,req['request']['state'],r['route'])
   offset=e['execution']['start_distance']-e['journey']['start_distance']
   samples=[{**p,'distance':p['distance']-offset} for p in e['journey']['samples'] if p['phase']=='executing' and p['distance']>=offset]
   samples.append(dict(xy=actual['xy'],heading=actual['heading'],distance=r['route']['length']))
   executed=audit_reverse(s,req['request']['state'],r['route'],actual=samples)
   checks.append(dict(case=name,action=action,planned=check,executed=executed))
  target=e['execution']['expected_finish'].get('node_id')
  line=s.nodes[target].baseline
  error=line.distance(point);angle=abs(angle_diff(tangent(line,point),actual['heading']))
  assert error<.15 and angle<.12,(name,action,error,angle)
  details=dict(case=name,action=action,target=target,baseline_error_m=error,heading_error=angle)
  if action.startswith('lane_change') or action=='select_lane':
   proof=r['route']['lane_change'];source=s.nodes[proof['source_corridor']].baseline
   at=source.interpolate(source.project(point));h=tangent(source,at)
   dx,dy=point.x-at.x,point.y-at.y;lateral=-dx*math.sin(h)+dy*math.cos(h)
   assert (lateral>1 if proof['lane_delta']<0 else lateral< -1),(action,lateral)
   assert abs(lateral)<6*abs(proof['lane_delta']),(action,lateral)
   details['signed_lateral_m']=lateral
   if action=='select_lane':
    entry=s.nodes[proof['target_entry_lane']]
    indices=[n.lane_index for n in s.graph.lane_groups[entry.lane_group]]
    extreme=min(indices) if req['request']['stage']['lane_reference']=='leftmost' else max(indices)
    assert entry.lane_index==extreme,(action,entry.key,entry.lane_index,indices)
    details['extreme_lane_rank_verified']=entry.lane_index
  if action=='u_turn' and r.get('phases'):
   yaw=abs(angle_diff(actual['heading'],e['journey']['origin']['heading']))
   assert yaw>2.9
   assert s.graph.surface.covers(footprint(actual['xy'],actual['heading'],4.8,2))
   details['actual_heading_reversal_degrees']=math.degrees(yaw)
  checks.append(details)
 right=next(e for e in events if c['start']<=e['time']<=c['end'] and e['type']=='completed' and e.get('route_source')=='C70254')
 from datetime import datetime
 stamp=lambda t:datetime.fromisoformat(t.replace('Z','+00:00'))
 continued=[e for e in events if e['type']=='telemetry' and e.get('session_id')==right['session_id'] and 0<(stamp(e['time'])-stamp(right['time'])).total_seconds()<10]
 assert continued
 for e in continued:
  pose=e['state'];line=s.nodes[pose['node_id']].baseline
  assert pose['node_id'] in ('L67605','C69782','L67695','C69338'),pose
  assert line.distance(Point(pose['xy']))<.15 and pose['speed']>.1
  assert s.graph.surface.buffer(.02).covers(footprint(pose['xy'],pose['heading'],4.8,2))
 checks.append(dict(case=name,automatic_continuation_verified=True,samples=len(continued),nodes=[e['state']['node_id'] for e in continued]))
(root/'results/browser-physical-destinations.json').write_text(json.dumps(checks,indent=2))
print(json.dumps(checks,indent=2))
