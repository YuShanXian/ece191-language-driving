import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
"""Independent raw-map and reverse-path checks for the ten browser examples."""
import sys,json,math
from pathlib import Path
from shapely.geometry import Point
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parent))
from engine.geometry import tangent,angle_diff,footprint
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'unit'))
from reverse_audit import audit_reverse
from fixtures import load_scene
cfg=json.loads((root/'results/browser-run-config.json').read_text());checks=[]
for name,c in cfg.items():
 if not c.get('end') or c.get('status')=='known_failure':continue
 scene=load_scene(c.get('scene',1));trace=c['traceRoot'].replace('\\','/')
 logs=Path(trace) if not (len(trace)>1 and trace[1]==':' and sys.platform!='win32') else Path('/mnt/'+trace[0].lower()+trace[2:])
 events=[json.loads(x) for x in (logs/'events.jsonl').read_text().splitlines()]
 for e in events:
  if not c['start']<=e['time']<=c['end'] or e['type']!='completed' or not e.get('request_id'):continue
  req=json.loads((logs/'requests'/(e['request_id']+'.json')).read_text());r=req['result']
  target=e['execution']['expected_finish'].get('node_id');line=scene.nodes[target].baseline
  error=line.distance(Point(e['state']['xy']));yaw=abs(angle_diff(tangent(line,Point(e['state']['xy'])),e['state']['heading']))
  assert error<.15 and yaw<.12,(name,e['action'],error,yaw)
  detail=dict(case=name,action=e['action'],baseline_error_m=error,heading_error=yaw,target=target)
  if e['action'].startswith('reverse'):
   detail['planned_reverse']=audit_reverse(scene,req['request']['state'],r['route'])
   offset=e['execution']['start_distance']-e['journey']['start_distance']
   samples=[{**p,'distance':p['distance']-offset} for p in e['journey']['samples'] if p['phase']=='executing' and p['distance']>=offset]
   samples.append(dict(xy=e['state']['xy'],heading=e['state']['heading'],distance=r['route']['length']))
   detail['executed_reverse']=audit_reverse(scene,req['request']['state'],r['route'],actual=samples)
  if e['action'].startswith('lane_change'):
   proof=r['route']['lane_change'];source=scene.nodes[proof['source_corridor']].baseline
   point=Point(e['state']['xy']);at=source.interpolate(source.project(point));h=tangent(source,at)
   lateral=-(point.x-at.x)*math.sin(h)+(point.y-at.y)*math.cos(h)
   assert (1<lateral<6 if proof['lane_delta']<0 else -6<lateral< -1),(name,lateral)
   detail['signed_lateral_m']=lateral
  # Independently inspect the entire observed journey, including approach.
  poses=[e['journey']['origin'],*e['journey']['samples'],e['state']]
  assert all(scene.graph.surface.buffer(.12).covers(footprint(p['xy'],p['heading'],4.8,2)) for p in poses),(name,'footprint left mapped drivable surface')
  detail['footprint_samples']=len(poses);checks.append(detail)
(root/'results/physical-audit.json').write_text(json.dumps(checks,indent=2))
print(json.dumps(checks,indent=2))
