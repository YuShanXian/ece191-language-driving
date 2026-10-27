"""One stage at a time. A failed maneuver keeps its place in the queue.

Retries are planned from the actual playback cursor. A waiting segment follows
connected roads for at most one second, never synthesizes a sideways recovery.
Only an instruction-faithful plan can transition from waiting to executing.
"""
import copy,json,math,heapq
import numpy as np
from functools import lru_cache
from mtr_project.paths import ROOT
from execute_language_plan_v4 import execute
from navigation_contract_v10 import normalize
from follow_road_v5 import build
from route_speed_v18 import sample

def validate_contract(value,schema,path='plan'):
 """Validate this project's primitive JSON contract without optional packages."""
 kinds=schema.get('type',[]);kinds=[kinds] if isinstance(kinds,str) else kinds
 types={'object':lambda v:isinstance(v,dict),'array':lambda v:isinstance(v,list),'string':lambda v:isinstance(v,str),'number':lambda v:type(v) in (float,int) and math.isfinite(v),'integer':lambda v:type(v)is int,'boolean':lambda v:type(v)is bool,'null':lambda v:v is None}
 if kinds and not any(types[k](value) for k in kinds):raise ValueError(path+': invalid type')
 if 'enum' in schema and value not in schema['enum']:raise ValueError(path+': unsupported value')
 if isinstance(value,dict):
  properties=schema.get('properties',{})
  if any(k not in value for k in schema.get('required',[])):raise ValueError(path+': missing field')
  if schema.get('additionalProperties') is False and any(k not in properties for k in value):raise ValueError(path+': unknown field')
  for k,v in value.items():
   if k in properties:validate_contract(v,properties[k],path+'.'+k)
 elif isinstance(value,list):
  if len(value)>1000:raise ValueError(path+': too many items')
  for i,v in enumerate(value):validate_contract(v,schema.get('items',{}),path+f'[{i}]')
 elif type(value) in (float,int):
  if value<schema.get('minimum',-math.inf) or value>schema.get('maximum',math.inf):raise ValueError(path+': out of range')

@lru_cache(1)
def manifest():return json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text())

def stage(action,**kw):
 return dict(action=action,source_clause=action.replace('_',' '),trigger='now',trigger_text='',trigger_value=None,target_text='',lane_reference='rightmost' if action in ('pull_over','park') else 'none',lane_number=None,completion_text='',constraints=[],travel_distance_m=10 if action=='reverse' else None,stop_at_end=action in ('reverse','pull_over','park'),target_speed_mps=None,**kw)

def accepted(result):
 if result.get('status')=='live_control':return True
 return (result.get('status')=='completed_offline' and len(result.get('points',[]))>1 and
         all(r.get('instruction_followed') is not False and not r.get('checks_overridden') and
             not r.get('stopped_at_road_end') and r.get('status') not in ('blocked','not_started','geometry_demo_only')
             and (r.get('requested_distance_m') is None or r.get('traveled_distance_m',0)>=r['requested_distance_m']-.2)
             for r in result.get('stages',[])))

def end_state(result,state):
 p=result['points'];h=result.get('heading_rad')
 heading=h[-1] if h else state['heading']
 if not h:
  for a in reversed(p[:-1]):
   d=np.asarray(p[-1])-a
   if np.linalg.norm(d)>.001:heading=float(math.atan2(d[1],d[0]));break
 out={**state,'xy':p[-1],'heading':heading,'speed':result['speed_mps'][-1],
      'history':(state.get('history',[])+p)[-3000:]}
 if result.get('is_reverse') and state.get('history'):
  history=state['history'];k=int(np.argmin(np.linalg.norm(np.asarray(history)-np.asarray(p[-1]),axis=1)))
  out['history']=history[:k+1]+[p[-1]]
 target=next((r.get('target') for r in reversed(result.get('stages',[])) if r.get('target')),None)
 if target:
  out['lane_key']=target
  out['lane_reversed']=next((r.get('target_reversed',False) for r in reversed(result.get('stages',[])) if r.get('target')),False)
 return out

def reason(result):return result.get('reason') or ' / '.join(r.get('reason','') for r in result.get('stages',[])) or result.get('status','No matching road')

def future_lane_opportunity(scene,plan,state,remaining,mode):
 """Search connected forward branches for a real lane-change opportunity.

 No lateral jump is used to create a missing lane. Every approach edge must be
 a forward map connection; the final maneuver uses the ordinary lane planner.
 """
 from free_navigation_v8 import context
 from navigation_turn_v15 import locate
 from shapely.geometry import Point
 from trajectory_checks import tangent,angle_diff
 g,initial,rot=context(scene);p0=initial[:2]+np.asarray(state['xy'])@rot.T;h0=initial[6]+state['heading']
 first=locate(g,p0,h0)
 if first is None or state.get('target_speed_mps',20/3.6)<=0:return None
 st=plan['stages'][0];target_speed=state.get('target_speed_mps',20/3.6);max_distance=max(5,target_speed*remaining)
 entry=g.nodes[first].baseline.project(Point(p0));heap=[(0.,0.,first,entry,[p0.tolist()],())];seen=set();candidates=0
 while heap and len(seen)<100:
  cost,distance,key,start,prior,path=heapq.heappop(heap)
  if key in seen or distance>max_distance:continue
  seen.add(key);node=g.nodes[key];line=node.baseline
  # Check early in each subsequent lane, leaving enough distance to merge.
  positions=[min(line.length-2,start+offset) for offset in (3.,10.,20.)] if node.kind=='lane' else []
  for pos in sorted(set(positions)):
   if pos<=start or distance+pos-start>max_distance:continue
   p=np.asarray(line.interpolate(pos).coords[0])[:2];h=tangent(line,p);normal=np.array([-math.sin(h),math.cos(h)])
   neighbors=[]
   for other in g.nodes.values():
    if other.kind!='lane' or other.lane_group!=node.lane_group or other.key==key:continue
    pp=np.asarray(other.baseline.interpolate(other.baseline.project(Point(p))).coords[0])[:2]
    lateral=float((pp-p)@normal)
    if abs(angle_diff(tangent(other.baseline,pp),h))>math.radians(25):continue
    if st['action']=='select_lane' or (1.5<lateral*(1 if st['action'].endswith('left') else -1)<7):neighbors.append(other)
   if not neighbors:continue
   tail=[list(line.interpolate(float(s)).coords[0])[:2] for s in np.r_[np.arange(start+.4,pos,.4),pos]]
   approach=np.asarray(prior+tail);local=(approach-initial[:2])@rot
   if len(local)<3:continue
   pp,vv=sample(local,target_speed,state['speed'])
   seconds=(len(pp)-1)*.1
   if seconds>remaining+.01:continue
   future={**state,'xy':pp[-1].tolist(),'heading':float(h-initial[6]),'speed':float(vv[-1]),'lane_key':key,'history':state.get('history',[])+pp.tolist()}
   candidates+=1;r=execute(scene,plan,future,mode)
   if not accepted(r):
    if candidates>=12:return None
    continue
   count=len(pp)-1;out=copy.deepcopy(r);out['points']=pp.tolist()+r['points'][1:];out['speed_mps']=vv.tolist()+r['speed_mps'][1:]
   prefix_head=[state['heading']]+[math.atan2(b[1]-a[1],b[0]-a[0]) for a,b in zip(pp[:-1],pp[1:])]
   rh=r.get('heading_rad') or [future['heading']]+[math.atan2(b[1]-a[1],b[0]-a[0]) for a,b in zip(r['points'][:-1],r['points'][1:])]
   out['heading_rad']=prefix_head+rh[1:]
   for row in out.get('stages',[]):row['start_point']=row.get('start_point',0)+count;row['end_point']=row.get('end_point',0)+count
   out.update(status='ready',approach_seconds=seconds,waiting_path=list(path)+( [key] ),reason=f'Continue on connected roads for {seconds:.1f} s, then execute the requested lane maneuver.',opportunity_wait=True)
   return out
  end=np.asarray(line.coords[-1])[:2];head=tangent(line,end);tail=[list(line.interpolate(float(s)).coords[0])[:2] for s in np.r_[np.arange(start+.4,line.length,.4),line.length]]
  for nk,relation in g.edges.get(key,{}).items():
   if relation!='forward' or nk in seen:continue
   other=g.nodes[nk].baseline;angle=abs(angle_diff(tangent(other,np.asarray(other.coords[-1])[:2]),head))
   length=max(0,line.length-start)
   heapq.heappush(heap,(cost+length+10*angle,distance+length,nk,0.,prior+tail,path+(key,)))
 return None

def waiting_motion(scene,state,seconds,why):
 route=build(next(w for w in manifest() if w['scene']==scene),state)
 stationary=lambda cause:dict(status='waiting',reason=why,dead_end=True,road_reason=cause,dt=.1,points=[state['xy']]* (max(1,round(seconds/.1))+1),speed_mps=[0.]*(max(1,round(seconds/.1))+1),heading_rad=[state['heading']]*(max(1,round(seconds/.1))+1),stages=[])
 def blocked(cause):return dict(status='road_blocked',dead_end=True,reason='No onward mapped route: '+cause+'. Pending steps are preserved; retry after changing the plan, or reset the scene.',road_reason=cause)
 if not route.get('available') or len(route.get('path',[]))<2:return blocked(route.get('reason','No connected onward road'))
 p=np.asarray(route['path'],float);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
 if arc[-1]<2.1:return blocked('At the end of connected map roads')
 # End two meters before the map boundary. The full speed envelope brakes for
 # this endpoint before taking a one-second prefix, so retries do not overshoot.
 length=arc[-1]-2;s=np.r_[arc[arc<length],length];p=np.column_stack([np.interp(s,arc,p[:,j]) for j in range(2)])
 target=state.get('target_speed_mps',20/3.6)
 # An explicitly stopped vehicle must not start moving just because a lane
 # change is pending. A maneuver from rest with a positive target may advance.
 if target<=0:return {**stationary('Target speed is zero; resume to move'),'dead_end':False}
 p,v=sample(p,target,state['speed'],stop=True)
 n=max(1,int(round(seconds/.1)));p=p[:n+1];v=v[:n+1]
 if len(p)<n+1:
  missing=n+1-len(p);p=np.vstack([p,np.repeat(p[-1][None,:],missing,axis=0)]);v=np.r_[v,np.zeros(missing)]
 headings=[state['heading']];last=state['heading']
 for a,b in zip(p[:-1],p[1:]):
  if np.linalg.norm(b-a)>.0001:last=float(math.atan2(b[1]-a[1],b[0]-a[0]))
  headings.append(last)
 return dict(status='waiting',reason=why,dead_end=False,dt=.1,points=p.tolist(),speed_mps=v.tolist(),heading_rad=headings,stages=[])

def plan_stage(scene,raw,state,remaining=20.,elapsed=0.,mode='free',next_action=None):
 if not 0<=remaining<=120 or not 0<=elapsed<=3600:raise ValueError('Invalid waiting budget')
 timed_out=dict(status='timed_out',reason='Waiting deadline reached; later stages remain pending.')
 def timeout_with_route():
  route=build(next(w for w in manifest() if w['scene']==scene),state)
  if route.get('available'):timed_out['follow_route']=route
  return timed_out
 plan=normalize(dict(status='parsed',stages=[copy.deepcopy(raw)],unresolved_text=[],explanation='Queued stage'))
 st=plan['stages'][0]
 if next_action in ('lane_change_left','lane_change_right'):st['next_action']=next_action
 if len(plan['stages'])!=1:raise ValueError('Expand relative multi-lane actions before executing the queue')
 trigger=st.get('trigger');value=st.get('trigger_value')
 if trigger=='elapsed_time' and isinstance(value,(int,float)) and value>=0:
  if elapsed+1e-6<value:return waiting_motion(scene,state,min(1.,remaining,max(.1,value-elapsed)),f'Waiting for the requested {value:g}-second delay') if remaining>=.099 else timeout_with_route()
  st.update(trigger='now',trigger_value=None,trigger_text='')
 result=execute(scene,plan,state,mode)
 if result.get('status')=='live_control' and st['action'] in ('continuous_drive','resume'):
  route=result.get('follow_route',{});p=np.asarray(route.get('path',[]))
  length=float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum()) if len(p)>1 else 0
  if not route.get('available') or length<2.1:
   return dict(status='road_blocked',dead_end=True,reason='No onward mapped route: '+route.get('reason','At the end of connected map roads')+'. Retry with a different maneuver or reset the scene; later steps remain queued.')
 if remaining>=.099 and not accepted(result) and st['action'] in ('lane_change_left','lane_change_right','select_lane') and st.get('trigger') in ('now','after_previous') and not any(st.get(k) for k in ('target_text','constraints','completion_text')):
  opportunity=future_lane_opportunity(scene,plan,state,remaining,mode)
  if opportunity:return opportunity
 if accepted(result):
  # The old turn planner searches arbitrarily far ahead. Do not claim an
  # executable-now turn whose junction lies outside the remaining wait window.
  approach=max((r.get('approach_distance_m',0) for r in result.get('stages',[])),default=0)
  if approach and result.get('points'):
   arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(np.asarray(result['points']),axis=0),axis=1))]
   approach_seconds=float(np.searchsorted(arc,approach)*result.get('dt',.1))
   if approach_seconds>remaining+.1:
    if remaining<.099:return timeout_with_route()
    return waiting_motion(scene,state,min(1.,remaining),'Requested junction is farther ahead; continuing and checking again')
   result['approach_seconds']=approach_seconds
  if st.get('target_speed_mps') is not None:result['target_speed_mps']=st['target_speed_mps']
  if result.get('follow_route',{}).get('roads'):result['follow_roads']=result['follow_route']['roads']
  result['status']='ready' if result['status']=='completed_offline' else result['status']
  return result
 if remaining>=.099:return waiting_motion(scene,state,min(1.,remaining),reason(result))
 return timeout_with_route()
