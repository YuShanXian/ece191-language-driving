"""Current-signal and wrong-direction annotations; never used to veto selection."""
import json,sqlite3,numpy as np
from shapely.geometry import Point
from mtr_project.paths import ROOT,write_json,sha256
from evaluate_candidate_checks import load_graph
from trajectory_checks import tangent,angle_diff,headings
base=ROOT/'runs/project-v3/instruction-priority-v6';data=json.loads((base/'results.json').read_text());results=[]
for w in data['windows']:
 src=w['source_window'];conv=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());run=ROOT/'runs'/src['run'];center=np.load(run/'internal_0000.npz')['center'];paths=np.load(base/f'scene-{w["scene"]:02d}-selected.npz')
 graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map'])
 dbpath=ROOT/'data/nuplan/db'/f'{src["clip"]}.db'
 with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as db:
  signals={'C'+str(k):status for k,status in db.execute('SELECT t.lane_connector_id,t.status FROM traffic_light_status t JOIN lidar_pc pc ON pc.record_id=t.lidar_pc_record_id WHERE pc.timestamp=?',(conv['current_timestamp_us'],))}
 for j,ch in enumerate(w['choices']):
  p=paths[f'command_{j}'] if f'command_{j}' in paths else np.load(ROOT/f'runs/project-v3/forced-direction-probes-v1/scene-{w["scene"]:02d}-command-{j}.npz')['points']
  h=headings(p,float(center[6]));visits={};opposite=[];ambiguous=[]
  for i,(xy,angle) in enumerate(zip(p,h)):
   aligned=[];opposed=[]
   for ix in graph.tree.query(Point(xy),predicate='intersects'):
    key=graph.keys[int(ix)];node=graph.nodes[key];delta=abs(np.degrees(angle_diff(angle,tangent(node.baseline,xy))))
    if node.kind=='connector' and key in signals and delta<45:visits.setdefault(key,[]).append(i)
    if node.kind=='lane':
     if delta<45:aligned.append(key)
     if delta>100:opposed.append(key)
   if opposed and not aligned:opposite.append(i)
   if opposed and aligned:ambiguous.append(i)
  lights=[{'connector':key,'current_status':signals[key],'first_sample_s':min(steps)*.1,'last_sample_s':max(steps)*.1,'sample_count':len(steps)} for key,steps in visits.items() if len(steps)>=3]
  streak=longest=0;last=-2
  for i in opposite:streak=streak+1 if i==last+1 else 1;last=i;longest=max(longest,streak)
  red=[r for r in lights if r['current_status']=='red'];green=[r for r in lights if r['current_status']=='green']
  flags=[]
  if red:flags.append('current_red_signal_on_overlapped_connector')
  if longest>=6:flags.append('sustained_opposite_lane_direction')
  record={'scene':w['scene'],'command':j,'current_timestamp_us':conv['current_timestamp_us'],'database_signal_rows':len(signals),'signal_associations':lights,'context_risk_flags':flags,
  'signal_association_ambiguous':bool(red and green),'opposite_lane_max_consecutive_steps':longest,
  'scope':'Current snapshot only. Polygon overlap plus heading association can be ambiguous, especially during forced crossings. Does not predict signal state at arrival or prove a traffic violation.'}
  results.append(record);print(w['scene'],j,'red',len(red),'green',len(green),'opposite_steps',longest,flush=True)
write_json(base/'context-risk.json',{'source_sha256':sha256(base/'results.json'),'results':results})
