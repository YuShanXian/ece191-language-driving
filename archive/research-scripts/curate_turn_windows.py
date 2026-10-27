"""Search existing logs by observed driving and map, never model outputs."""
import json,sqlite3,numpy as np
from datetime import datetime,timezone
from collections import Counter
from nuplan.database.nuplan_db.nuplan_scenario_queries import get_ego_state_for_lidarpc_record_id_from_db as ego_state
from evaluate_candidate_checks import load_graph
from audit_scene_context import metadata,forward_search
from trajectory_checks import angle_diff,tangent,footprint
from mtr_project.paths import ROOT,write_json,sha256

def main():
 out=ROOT/'runs/project-v3/curated-turn-windows'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');out.mkdir(parents=True)
 spec={'scope':'Retrospective case selection using recorded future, not an unbiased benchmark. Future never used as model input. No MTR output inspected.', 'speed_min_mps':1,'future_heading_abs_deg':[30,120],'past_heading_abs_max_deg':15,'anchor_spacing_seconds':.5,'event_separation_seconds':8,'anchors_per_event':5,'entry_distance_max_m':35,'strict_checks':'Observed-history lane match; future connected route and full-body map check. Failed cases retained in audit.'}
 write_json(out/'specification.json',spec)
 map_path=ROOT/'data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg';meta,edges=metadata(map_path)
 all_rows=[];inventories=[]
 for db in sorted((ROOT/'data/nuplan/db').glob('*.db')):
  with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as con:
   location=con.execute('select location from log').fetchone()[0]
   if location!='las_vegas':inventories.append({'clip':db.stem,'skipped':location});continue
   frames=con.execute('select p.timestamp,p.record_id,e.x,e.y,e.qw,e.qx,e.qy,e.qz,e.vx,e.vy,e.epsg from lidar_pc p join ego_pose e on p.ego_pose_record_id=e.record_id order by p.timestamp').fetchall()
  numeric=np.asarray([[r[j] for j in range(2,11)] for r in frames],float);w,x,y,z=numeric[:,2:6].T
  heading=np.unwrap(np.arctan2(2*(w*z+x*y),1-2*(y*y+z*z)))
  proposals=[]
  for i in range(42,len(frames)-120,10):
   speed=float(np.linalg.norm(numeric[i,:2]-numeric[i-2,:2])/((frames[i][0]-frames[i-2][0])/1e6))
   future=float(np.degrees(heading[i+120]-heading[i]));past=float(np.degrees(heading[i]-heading[i-40]))
   if speed<1 or not 30<=abs(future)<=120 or abs(past)>15:continue
   proposals.append({'index':i,'speed':speed,'future':future,'past':past,'action':'left' if future>0 else 'right'})
  groups=[]
  for q in proposals:
   if not groups or q['action']!=groups[-1][-1]['action'] or frames[q['index']][0]-frames[groups[-1][-1]['index']][0]>8e6:groups.append([])
   groups[-1].append(q)
  inventories.append({'clip':db.stem,'sha256':sha256(db),'duration_s':(frames[-1][0]-frames[0][0])/1e6,'proposal_anchors':len(proposals),'events':len(groups)})
  for event_index,group in enumerate(groups):
   # Prefer earliest moving approach; requiring 75deg prematurely favored already-entered connectors.
   ranked=sorted(group,key=lambda q:q['index'])
   selected=[]
   for q in ranked:
    if all(abs(q['index']-p['index'])>=20 for p in selected):selected.append(q)
    if len(selected)==5:break
   for q in selected:
    i=q['index'];ts=np.asarray([frames[j][0] for j in range(i-40,i+121,2)]);es=[ego_state(str(db),frames[j][1].hex()) for j in range(i-40,i+121,2)]
    origin=np.array([es[20].center.x,es[20].center.y]);xy=np.array([[e.center.x,e.center.y] for e in es])-origin;h=np.array([e.center.heading for e in es])
    g=load_graph(origin,int(frames[i][10]),map_path);history=g.match(xy[:21],h[0]);current=history['node_sequence'][-1] if history['matched'] else None
    future=g.match(xy[20:],h[20],start_nodes={current}) if current else {'matched':False,'failure':'history_unmatched'}
    body=g.body_check(xy[20:],h[20],es[20].car_footprint.length,es[20].car_footprint.width)
    info={k:dict(v) for k,v in meta.items()}
    for k,v in info.items():
     if k not in g.nodes:continue
     b=g.nodes[k].baseline;change=float(np.degrees(angle_diff(tangent(b,b.coords[-1]),tangent(b,b.coords[0]))))
     v['type']='STRAIGHT' if abs(change)<30 else ('UTURN' if abs(change)>=150 else ('LEFT' if change>0 else 'RIGHT'))
    search=forward_search(g,current,xy[20],info,edges,70) if current else {'connectors':[]}
    target=[v for v in search['connectors'] if v['turn_type']==q['action'].upper() and not v['already_occupied'] and v['distance_to_entry_m']<=35]
    reasons=[]
    if not history['matched']:reasons.append('history_unmatched')
    if current and g.nodes[current].kind!='lane':reasons.append('already_in_connector')
    if not target:reasons.append('no_direct_near_turn')
    if not future['matched']:reasons.append('recorded_route_unmatched')
    if not body['passed']:reasons.append('recorded_body_outside')
    if np.max(abs(np.diff(ts)/1e6-.1))>.002:reasons.append('timestamp_gap')
    row={'clip':db.stem,'source_db':str(db.relative_to(ROOT)),'timestamp_us':frames[i][0],'seconds':(frames[i][0]-frames[0][0])/1e6,'event':event_index,'action':q['action'],'speed_mps':q['speed'],'past_heading_deg':q['past'],'future_heading_deg':q['future'],'current_node':current,'near_turns':target,'route':future,'body':body,'rejection_reasons':reasons,'accepted':not reasons,'origin_xy_m':origin.tolist(),'source_epsg':int(frames[i][10])}
    all_rows.append(row);print(json.dumps({k:row[k] for k in ['clip','seconds','action','accepted','rejection_reasons']}),flush=True)
    if not reasons:
     np.savez_compressed(out/(db.stem+'_'+str(frames[i][0])+'.npz'),xy=xy,heading=h,timestamps=ts)
   write_json(out/'progress.json',{'inventory':inventories,'candidates':all_rows})
 accepted=[r for r in all_rows if r['accepted']];chosen=[]
 for r in accepted:
  if not any(p['clip']==r['clip'] and p['event']==r['event'] for p in chosen):chosen.append(r)
 report={'specification':spec,'inventory':inventories,'candidates':all_rows,'selected':chosen,'summary':{'inspected_anchors':len(all_rows),'accepted_anchors':len(accepted),'distinct_selected_events':len(chosen),'directions':dict(Counter(r['action'] for r in chosen))},'source_map_sha256':sha256(map_path),'implementation_sha256':sha256(ROOT/'scripts/curate_turn_windows.py')}
 write_json(out/'selection.json',report);print(json.dumps({'output':str(out),'summary':report['summary']}),flush=True)
if __name__=='__main__':main()
