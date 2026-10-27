"""Offline sequential map planner. Replans from evolving state; never substitutes missing actions."""
import argparse,json,copy
import numpy as np
from shapely.geometry import Point
from mtr_project.paths import ROOT
from evaluate_candidate_checks import load_graph
from automatic_road_selector import select_road
from centerline_trajectory_planner import geometry,time_parameterize,CONFIG
from trajectory_checks import tangent,angle_diff
from distance_motion_v3 import distance_motion
CANON={'go_straight':'Go straight','keep_lane':'Go straight','turn_left':'Turn left','turn_right':'Turn right','lane_change_left':'Change lanes to the left','lane_change_right':'Change lanes to the right'}

def execute(scene,plan,initial_state=None,mode="safe"):
 manifest=json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text());w=next(w for w in manifest if w['scene']==scene)
 c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());graph=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map'])
 environment_path=ROOT/'runs/project-v3/environment-grounding-v1/contexts.json'
 environment=next((x for x in json.loads(environment_path.read_text()) if x['scene']==scene and x['timestamp_us']==c['current_timestamp_us']),None) if environment_path.exists() else None
 center=np.load(ROOT/'runs'/w['run']/'internal_0000.npz')['center'].astype(float).copy();initial=center.copy();states=[];points=[center[:2].copy()];speeds=[float(np.linalg.norm(center[7:9]))];acc=np.zeros(2)
 if initial_state is not None:
  xy=np.asarray(initial_state['xy'],dtype=float);heading=float(initial_state['heading']);speed=float(initial_state['speed'])
  if xy.shape!=(2,) or not np.isfinite([*xy,heading,speed]).all() or np.linalg.norm(xy)>2000 or not 0<=speed<=30:raise ValueError('Invalid live state')
  h=initial[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]])
  center[:2]=initial[:2]+xy@rot.T;center[6]=initial[6]+heading;center[7:9]=speed*np.array([np.cos(center[6]),np.sin(center[6])]);points=[center[:2].copy()];speeds=[speed];environment=None
 def finish(status):
  h=initial[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]])
  return {'environment_at_initial_pose':environment,'scene':scene,'status':status,'stages':states,'points':np.round((np.asarray(points)-initial[:2])@rot,4).tolist(),'speed_mps':speeds,'dt':.1,'scope':'New offline map trajectories from evolving state. No reactive traffic, visual referent grounding or live vehicle commands. Stage completion is geometry only.'}
 if plan.get('status')!='parsed' or plan.get('unresolved_text'):return finish('needs_clarification')
 if not isinstance(plan.get('stages'),list) or not 1<=len(plan['stages'])<=12:return finish('invalid_plan')
 for idx,st in enumerate(plan['stages']):
  row={'index':idx,'action':st['action'],'source_clause':st['source_clause'],'start_point':len(points)-1,'start_xy':center[:2].tolist()};states.append(row)
  def block(reason,status='blocked'):
   row.update(status=status,reason=reason,end_point=len(points)-1);return finish('partial' if idx else status)
  if st['trigger'] not in ('now','after_previous'):
   route=next((x for x in (environment or {}).get('routes',[]) if x['instruction']==CANON.get(st['action'])),None) if idx==0 else None
   if route:row['environment_evidence']=route
   statuses=', '.join(x['id']+'='+x['signal']['classification'] for x in (route or {}).get('connectors',[]))
   suffix=(' Exact-current route signal observations: '+statuses+'.') if statuses else ''
   if st['trigger']=='stop_sign' and route:
    stops=sorted({z['id'] for x in route.get('connectors',[]) for z in x['stop_regions'] if (z.get('region') or {}).get('sdk_enum')=='STOP_SIGN'})
    if stops:suffix+=' Map-associated stop-sign regions: '+', '.join(stops)+'. Arrival and stopping have not been established.'
   return block('Needs observed trigger: '+st['trigger']+' / '+st['trigger_text']+suffix,'waiting_for_observation')
  unknown_constraints=[x for x in st['constraints'] if x.strip().lower() not in ('\u6cbf\u8def','\u6cbf\u9053\u8def','\u6cbf\u7740\u9053\u8def','along the road','follow the road')]
  if unknown_constraints:return block('Needs constraint checking: '+ '; '.join(unknown_constraints))
  generic_lane=st['action'] in ('lane_change_left','lane_change_right') and st['target_text'].strip().lower() in ('the left lane','the right lane','left lane','right lane','the lane to the left','the lane to the right')
  if st['target_text'] and st['action']!='select_lane' and not generic_lane:return block('Needs grounded target: '+st['target_text'])
  if st['completion_text']:return block('Explicit completion condition not implemented: '+st['completion_text'])
  distance=st.get('travel_distance_m');stop_at_end=st.get('stop_at_end',False)
  if distance is not None and (type(distance) not in (int,float) or not np.isfinite(distance) or not 0<distance<=200):return block('Distance must be between 0 and 200 meters.')
  if distance is not None and st['action'] not in ('go_straight','keep_lane'):return block('Distance must be a separate drive stage after the maneuver.')
  action=st['action'];config=copy.deepcopy(CONFIG);config['horizon_s']=20.
  requested_speed=st.get('target_speed_mps')
  if requested_speed is not None:
   if type(requested_speed) not in (float,int) or not 0<requested_speed<=15:return block('Driving speed must be above 0 and at most 15 m/s.')
   config['cruise_speed_mps']=requested_speed
   row['target_speed_mps']=requested_speed
  mapped_uturn=None
  if action=='u_turn' and mode=='safe':
   from uturn_map_v7 import find_uturn
   probe=select_road(graph,center,'Go straight')
   if probe.get('current'):mapped_uturn=find_uturn(graph,center,probe['current']['key'])
  if action=='u_turn' and not mapped_uturn:
   from generated_uturn_v7 import generate
   try:segment,timing,heading,info=generate(graph,center,acc,free=mode=="free")
   except ValueError as exc:return block(str(exc))
   points.extend(segment[1:]);speeds.extend(timing['speed_mps'][1:]);center[:2]=segment[-1];center[6]=heading;center[7:9]=timing['speed_mps'][-1]*np.array([np.cos(heading),np.sin(heading)]);acc=np.zeros(2)
   row.update(info);row.update(status='completed_offline' if info['body_check_passed'] and info['target'] else 'geometry_demo_only',end_point=len(points)-1,end_xy=center[:2].tolist(),traveled_distance_m=float(np.linalg.norm(np.diff(segment,axis=0),axis=1).sum()),final_speed_mps=float(timing['speed_mps'][-1]),stop_at_end=timing['speed_mps'][-1]<.05,generated_duration_s=(len(segment)-1)*.1)
   if mode=='safe' and (not info['body_check_passed'] or not info['target'] or info['max_steering_rad']>CONFIG['steering_limit_rad']):return block('Generated U-turn failed conservative map checks.','review_required')
   continue
  if action=='hold_stopped':
   if np.linalg.norm(center[7:9])>.2:return block('Vehicle is moving; hold-stopped does not imply a stop maneuver.')
   row.update(status='holding',reason='Maintaining stopped state; no duration or release event supplied.',end_point=len(points)-1);return finish('holding')
  if action not in (*CANON,'select_lane','stop','slow_down','speed_up','resume','u_turn'):return block('Execution capability missing: '+action)
  if st['lane_number'] not in (None,1) and action!='select_lane':return block('Multiple relative lane changes need explicit per-lane completion.')
  query=CANON.get(action,'Go straight');road=select_road(graph,center,query)
  if action in ('go_straight','keep_lane','stop','resume','slow_down','speed_up','lane_change_left','lane_change_right','select_lane'):
   from navigation_turn_v15 import locate
   live_key=locate(graph,center[:2],center[6])
   if live_key is not None:
    road={'status':'selected','reason':'follow_current_map_segment','current':{'key':live_key},'selected':{'path':[live_key],'target':live_key}}
  if road.get('status')!='selected' and action in ('go_straight','keep_lane','stop','resume','slow_down','speed_up','u_turn'):
   candidates=[]
   for node in graph.nodes.values():
    distance_to_line=node.baseline.distance(Point(center[:2]));angle=abs(angle_diff(tangent(node.baseline,center[:2]),center[6]))
    if distance_to_line<3 and angle<np.radians(45) and node.polygon.covers(Point(center[:2])):candidates.append((distance_to_line,angle,node.key))
   if candidates:
    key=min(candidates)[2];road={'status':'selected','reason':'follow_current_map_segment','current':{'key':key},'selected':{'path':[key],'target':key}}
  if road.get('status')!='selected':return block('No suitable map road from the current position and heading.')
  if action in ('turn_left','turn_right') and road['reason']!='requested_turn':return block('Requested turn not available; continuing straight is not success.')
  if action.startswith('lane_change'):
   current_node=graph.nodes[road['current']['key']];normal=np.array([-np.sin(center[6]),np.cos(center[6])]);sign=1 if action.endswith('left') else -1;neighbors=[]
   for node in graph.nodes.values():
    if node.kind!='lane' or node.lane_group!=current_node.lane_group or node.key==current_node.key:continue
    q=np.array(node.baseline.interpolate(node.baseline.project(Point(center[:2]))).coords[0])[:2];side=float((q-center[:2])@normal)
    if 1.5<sign*side<7 and abs(angle_diff(tangent(node.baseline,q),center[6]))<np.radians(25):neighbors.append((abs(side),node.key))
   if neighbors:
    key=min(neighbors)[1];road['selected']={'path':[key],'target':key};road['reason']='adjacent_onward_lane'
   elif road['reason']!='adjacent_onward_lane':return block('No matching adjacent lane found at the current vehicle position.')
  keys=road['selected']['path'];target=road['selected']['target']
  if action=='u_turn':
   from uturn_map_v7 import find_uturn
   route=find_uturn(graph,center,road['current']['key'])
   if not route:return block('No connected U-turn route found in the loaded map from this position.')
   keys=route;target=route[-1];road['reason']='connected_map_uturn';config['horizon_s']=60.;config['cruise_speed_mps']=min(config['cruise_speed_mps'],4.)
  if action=='select_lane':
   n=graph.nodes[road['current']['key']];normal=np.array([-np.sin(center[6]),np.cos(center[6])]);pos=Point(center[:2])
   group=[x for x in graph.nodes.values() if x.kind=='lane' and x.lane_group==n.lane_group and abs(angle_diff(tangent(x.baseline,center[:2]),center[6]))<np.radians(30)]
   group.sort(key=lambda x:float((np.asarray(x.baseline.interpolate(x.baseline.project(pos)).coords[0])[:2]-center[:2])@normal),reverse=st['lane_reference']=='leftmost')
   number=st['lane_number']
   if st['lane_reference'] not in ('leftmost','rightmost') or type(number) is not int or not 1<=number<=len(group):return block('Requested ordinal lane does not exist in the current same-direction lane group.')
   target=group[number-1].key;keys=[target];road['reason']='ordinal_lane_by_physical_left_right'
  if action in ('go_straight','keep_lane') and distance is None and idx<len(plan['stages'])-1:return block('Straight/keep-lane has no specified completion point before the next action.')
  completion_key=keys[-1]
  for _ in range(12):
   if sum(graph.nodes[k].baseline.length for k in keys)>max(90,(distance or 0)+30):break
   nxt=[k for k,r in graph.edges.get(keys[-1],{}).items() if r=='forward' and k not in keys]
   if not nxt:break
   end=np.asarray(graph.nodes[keys[-1]].baseline.coords[-1])[:2];heading=tangent(graph.nodes[keys[-1]].baseline,end)
   nxt.sort(key=lambda k:abs(angle_diff(tangent(graph.nodes[k].baseline,np.asarray(graph.nodes[k].baseline.coords[0])[:2]),heading)))
   keys=keys+[nxt[0]]
  v0=float(np.linalg.norm(center[7:9]))
  if action=='stop':config['cruise_speed_mps']=0.
  elif action=='slow_down':config['cruise_speed_mps']=max(0.,v0*.5)
  elif action=='speed_up':config['cruise_speed_mps']=min(10.,v0+2.)
  options=[];geometry_errors=[]
  for join in ([2.,4.,6.]+CONFIG['join_distances_m'] if action.startswith('lane_change') else CONFIG['join_distances_m']):
   try:
    shape=geometry(graph,keys,center,join)
    effective_distance=min(distance,max(0.,shape['length']-max(3.,float(center[3])/2+1.5))) if distance is not None else None
    truncated=distance is not None and effective_distance<distance
    if distance is not None and effective_distance<.1:raise ValueError('Already at the end of the available road.')
    p,timing=distance_motion(shape,center,acc,effective_distance,stop_at_end or truncated,config) if distance is not None else time_parameterize(shape,center,acc,config)
    timing['effective_distance_m']=effective_distance;timing['stopped_at_road_end']=truncated
    body=graph.body_check(p,float(center[6]),float(center[3]),float(center[4]));steer=float(np.max(np.abs(np.arctan(CONFIG['wheelbase_m']*shape['curvature']))))
    options.append((len(body['outside_sample_steps']),steer,p,timing,shape))
   except (ValueError,IndexError) as exc:
    geometry_errors.append(str(exc));continue
  if not options:return block(geometry_errors[0] if geometry_errors and all(e.startswith('Requested ') for e in geometry_errors) else 'No executable trajectory: '+ '; '.join(sorted(set(geometry_errors))))
  if action.startswith('lane_change') or action=='select_lane':
   node=graph.nodes[completion_key]
   def reaches_target(option):
    pp=option[2];streak=0
    for j in range(1,len(pp)):
     d=pp[j]-pp[j-1];ok=np.linalg.norm(d)>.001 and node.polygon.covers(Point(pp[j])) and node.baseline.distance(Point(pp[j]))<1 and abs(angle_diff(np.arctan2(d[1],d[0]),tangent(node.baseline,pp[j])))<np.radians(20)
     streak=streak+1 if ok else 0
     if streak>=8:return True
    return False
   valid=[o for o in options if o[0]==0 and o[1]<=CONFIG['steering_limit_rad'] and reaches_target(o)]
   if valid:options=valid
  _,steer,p,timing,shape=min(options,key=lambda x:(x[1]>CONFIG['steering_limit_rad'],x[0],x[1]))
  cut=len(p)-1;complete=False
  if distance is not None:
   complete=True
  elif action=='stop':
   hits=[i for i,v in enumerate(timing['speed_mps']) if i>0 and v<.1]
   if hits:cut=hits[0];complete=True
  elif action in ('slow_down','speed_up','resume'):
   hits=[i for i,v in enumerate(timing['speed_mps']) if i>=10 and abs(v-config['cruise_speed_mps'])<.3]
   if hits:cut=hits[0];complete=True
  elif action in ('turn_left','turn_right','lane_change_left','lane_change_right','select_lane','u_turn'):
   endnode=graph.nodes[completion_key];streak=0
   completion_nodes=[endnode]
   if action.startswith('lane_change') or action=='select_lane':
    # A lane is split into map segments. Its forward continuation is still the same selected lane corridor.
    for k in keys[1:3]:
     n=graph.nodes[k]
     if abs(angle_diff(tangent(n.baseline,np.asarray(n.baseline.coords[-1])[:2]),tangent(endnode.baseline,np.asarray(endnode.baseline.coords[-1])[:2])))<np.radians(25):completion_nodes.append(n)
   for i in range(1,len(p)):
    delta=p[i]-p[i-1];heading=float(np.arctan2(delta[1],delta[0]));ok=np.linalg.norm(delta)>.001 and any(n.polygon.covers(Point(p[i])) and n.baseline.distance(Point(p[i]))<1.0 and abs(angle_diff(heading,tangent(n.baseline,p[i])))<np.radians(20) for n in completion_nodes)
    streak=streak+1 if ok else 0
    if streak>=8:cut=i;complete=True;break
  else:complete=idx==len(plan['stages'])-1
  segment=p[:cut+1];sv=timing['speed_mps'][:cut+1].copy()
  if action=='stop' and complete:sv[-1]=0.;stop_at_end=True
  traveled=float(np.linalg.norm(np.diff(segment,axis=0),axis=1).sum());row.update(requested_distance_m=distance,traveled_distance_m=traveled,stop_at_end=stop_at_end,final_speed_mps=float(sv[-1]))
  if distance is not None:
   row['effective_distance_m']=timing['effective_distance_m'];row['stopped_at_road_end']=timing['stopped_at_road_end']
   if timing['stopped_at_road_end']:
    row['reason']=f'Requested {distance:.0f} m; drove {traveled:.1f} m and stopped at the end of the available road.';row['stop_at_end']=True
   row['distance_error_m']=abs(traveled-timing['effective_distance_m'])
   complete=complete and row['distance_error_m']<.25 and (not (stop_at_end or timing['stopped_at_road_end']) or sv[-1]<.05)
  body=graph.body_check(segment,float(center[6]),float(center[3]),float(center[4]));row.update(target=target,path=keys,road_reason=road['reason'],body_check_passed=body['passed'],max_steering_rad=steer,generated_duration_s=cut*.1)
  points.extend(segment[1:]);speeds.extend(sv[1:]);row['end_point']=len(points)-1
  center[:2]=segment[-1]
  for prior in reversed(segment[:-1]):
   delta=segment[-1]-prior
   if np.linalg.norm(delta)>.01:
    center[6]=np.arctan2(delta[1],delta[0]);break
  center[7:9]=sv[-1]*np.array([np.cos(center[6]),np.sin(center[6])]);acc=float(timing['longitudinal_accel_mps2'][cut])*np.array([np.cos(center[6]),np.sin(center[6])]);row['end_xy']=center[:2].tolist()
  if not complete:return block('Action did not reach its geometric completion within the generated horizon.','incomplete')
  if not body['passed'] or steer>CONFIG['steering_limit_rad']:
   if mode=='safe':return block('Generated path violates a road-body or steering check; later stages not advanced.','review_required')
   row['warning']='Free mode: road-boundary or steering check failed; simulated motion allowed.'
   row['checks_overridden']=True
  row['status']='completed_offline'
  if timing.get('stopped_at_road_end'):
   for j,later in enumerate(plan['stages'][idx+1:],idx+1):states.append({'index':j,'action':later['action'],'source_clause':later['source_clause'],'status':'not_started','reason':'Stopped at map end before this step.','start_point':len(points)-1,'end_point':len(points)-1})
   return finish('completed_offline')
 return finish('completed_offline')

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--scene',type=int,required=True,choices=range(1,8));a.add_argument('--plan',required=True);args=a.parse_args()
 from pathlib import Path
 planpath=Path(args.plan);plan=json.loads(planpath.read_text(encoding='utf-8-sig'));result=execute(args.scene,plan);out=planpath.parent/'execution.json';out.write_text(json.dumps(result,indent=2));print(json.dumps({'status':result['status'],'stages':result['stages'],'output':str(out)},indent=2))

