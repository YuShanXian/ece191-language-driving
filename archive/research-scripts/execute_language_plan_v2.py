"""Offline sequential map planner. Replans from evolving state; never substitutes missing actions."""
import argparse,json,copy
import numpy as np
from shapely.geometry import Point
from mtr_project.paths import ROOT
from evaluate_candidate_checks import load_graph
from automatic_road_selector import select_road
from centerline_trajectory_planner import geometry,time_parameterize,CONFIG
from trajectory_checks import tangent,angle_diff
CANON={'go_straight':'Go straight','keep_lane':'Keep lane','turn_left':'Turn left','turn_right':'Turn right','lane_change_left':'Change lanes to the left','lane_change_right':'Change lanes to the right'}

def execute(scene,plan):
 manifest=json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text());w=next(w for w in manifest if w['scene']==scene)
 c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());graph=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map'])
 environment_path=ROOT/'runs/project-v3/environment-grounding-v1/contexts.json'
 environment=next((x for x in json.loads(environment_path.read_text()) if x['scene']==scene and x['timestamp_us']==c['current_timestamp_us']),None) if environment_path.exists() else None
 center=np.load(ROOT/'runs'/w['run']/'internal_0000.npz')['center'].astype(float).copy();initial=center.copy();states=[];points=[center[:2].copy()];speeds=[float(np.linalg.norm(center[7:9]))];acc=np.zeros(2)
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
  if st['constraints']:return block('Needs constraint checking: '+ '; '.join(st['constraints']))
  generic_lane=st['action'] in ('lane_change_left','lane_change_right') and st['target_text'].strip().lower() in ('the left lane','the right lane','left lane','right lane','the lane to the left','the lane to the right')
  if st['target_text'] and st['action']!='select_lane' and not generic_lane:return block('Needs grounded target: '+st['target_text'])
  if st['completion_text']:return block('Explicit completion condition not implemented: '+st['completion_text'])
  action=st['action'];config=copy.deepcopy(CONFIG);config['horizon_s']=20.
  if action=='hold_stopped':
   if np.linalg.norm(center[7:9])>.2:return block('Vehicle is moving; hold-stopped does not imply a stop maneuver.')
   row.update(status='holding',reason='Maintaining stopped state; no duration or release event supplied.',end_point=len(points)-1);return finish('holding')
  if action not in (*CANON,'select_lane','stop','slow_down','speed_up','resume'):return block('Execution capability missing: '+action)
  if st['lane_number'] not in (None,1) and action!='select_lane':return block('Multiple relative lane changes need explicit per-lane completion.')
  query=CANON.get(action,'Go straight');road=select_road(graph,center,query)
  if road.get('status')!='selected':return block('No map road from the current state.')
  if action in ('turn_left','turn_right') and road['reason']!='requested_turn':return block('Requested turn not available; continuing straight is not success.')
  if action.startswith('lane_change') and road['reason']!='adjacent_onward_lane':return block('Requested neighboring lane not found; no silent fallback.')
  keys=road['selected']['path'];target=road['selected']['target']
  if action=='select_lane':
   n=graph.nodes[road['current']['key']];normal=np.array([-np.sin(center[6]),np.cos(center[6])]);pos=Point(center[:2])
   group=[x for x in graph.nodes.values() if x.kind=='lane' and x.lane_group==n.lane_group and abs(angle_diff(tangent(x.baseline,center[:2]),center[6]))<np.radians(30)]
   group.sort(key=lambda x:float((np.asarray(x.baseline.interpolate(x.baseline.project(pos)).coords[0])[:2]-center[:2])@normal),reverse=st['lane_reference']=='leftmost')
   number=st['lane_number']
   if st['lane_reference'] not in ('leftmost','rightmost') or type(number) is not int or not 1<=number<=len(group):return block('Requested ordinal lane does not exist in the current same-direction lane group.')
   target=group[number-1].key;keys=[target];road['reason']='ordinal_lane_by_physical_left_right'
  if action in ('go_straight','keep_lane') and idx<len(plan['stages'])-1:return block('Straight/keep-lane has no specified completion point before the next action.')
  completion_key=keys[-1]
  for _ in range(3):
   if sum(graph.nodes[k].baseline.length for k in keys)>90:break
   nxt=[k for k,r in graph.edges.get(keys[-1],{}).items() if r=='forward' and k not in keys]
   if len(nxt)!=1:break
   keys=keys+nxt
  v0=float(np.linalg.norm(center[7:9]))
  if action=='stop':config['cruise_speed_mps']=0.
  elif action=='slow_down':config['cruise_speed_mps']=max(0.,v0*.5)
  elif action=='speed_up':config['cruise_speed_mps']=min(10.,v0+2.)
  options=[]
  for join in CONFIG['join_distances_m']:
   try:
    shape=geometry(graph,keys,center,join);p,timing=time_parameterize(shape,center,acc,config);body=graph.body_check(p,float(center[6]),float(center[3]),float(center[4]));steer=float(np.max(np.abs(np.arctan(CONFIG['wheelbase_m']*shape['curvature']))))
    options.append((len(body['outside_sample_steps']),steer,p,timing,shape))
   except (ValueError,IndexError):continue
  if not options:return block('The target lane has insufficient usable forward geometry at this starting position; a longer or earlier map window is needed.')
  _,steer,p,timing,shape=min(options,key=lambda x:(x[1]>CONFIG['steering_limit_rad'],x[0],x[1]))
  cut=len(p)-1;complete=False
  if action=='stop':
   hits=[i for i,v in enumerate(timing['speed_mps']) if i>0 and v<.1]
   if hits:cut=hits[0];complete=True
  elif action in ('slow_down','speed_up','resume'):
   hits=[i for i,v in enumerate(timing['speed_mps']) if i>=10 and abs(v-config['cruise_speed_mps'])<.3]
   if hits:cut=hits[0];complete=True
  elif action in ('turn_left','turn_right','lane_change_left','lane_change_right','select_lane'):
   endnode=graph.nodes[completion_key];streak=0
   for i in range(1,len(p)):
    delta=p[i]-p[i-1];heading=float(np.arctan2(delta[1],delta[0]));ok=np.linalg.norm(delta)>.001 and endnode.polygon.covers(Point(p[i])) and endnode.baseline.distance(Point(p[i]))<1.0 and abs(angle_diff(heading,tangent(endnode.baseline,p[i])))<np.radians(20)
    streak=streak+1 if ok else 0
    if streak>=8:cut=i;complete=True;break
  else:complete=idx==len(plan['stages'])-1
  segment=p[:cut+1];sv=timing['speed_mps'][:cut+1]
  body=graph.body_check(segment,float(center[6]),float(center[3]),float(center[4]));row.update(target=target,path=keys,road_reason=road['reason'],body_check_passed=body['passed'],max_steering_rad=steer,generated_duration_s=cut*.1)
  points.extend(segment[1:]);speeds.extend(sv[1:]);row['end_point']=len(points)-1
  center[:2]=segment[-1];delta=segment[-1]-segment[max(0,len(segment)-3)]
  if np.linalg.norm(delta)>.001:center[6]=np.arctan2(delta[1],delta[0])
  center[7:9]=sv[-1]*np.array([np.cos(center[6]),np.sin(center[6])]);acc=float(timing['longitudinal_accel_mps2'][cut])*np.array([np.cos(center[6]),np.sin(center[6])]);row['end_xy']=center[:2].tolist()
  if not complete:return block('Action did not reach its geometric completion within the generated horizon.','incomplete')
  if not body['passed'] or steer>CONFIG['steering_limit_rad']:
   return block('Generated path violates a road-body or steering check; later stages not advanced.','review_required')
  row['status']='completed_offline'
 return finish('completed_offline')

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--scene',type=int,required=True,choices=range(1,8));a.add_argument('--plan',required=True);args=a.parse_args()
 from pathlib import Path
 planpath=Path(args.plan);plan=json.loads(planpath.read_text(encoding='utf-8-sig'));result=execute(args.scene,plan);out=planpath.parent/'execution.json';out.write_text(json.dumps(result,indent=2));print(json.dumps({'status':result['status'],'stages':result['stages'],'output':str(out)},indent=2))
