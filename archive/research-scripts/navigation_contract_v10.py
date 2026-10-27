"""Normalize redundant descriptors without dropping real destinations or conditions."""
import copy,re
def normalize(plan):
 p=copy.deepcopy(plan)
 for s in p.get('stages',[]):
  action=s.get('action')
  if action=='reverse' and s.get('completion_text','').strip().lower() in ('a little','a bit','slightly','\u4e00\u70b9','\u4e00\u70b9\u70b9') and s.get('travel_distance_m') is None:
   s['completion_text']='';s['travel_distance_m']=2.;s['stop_at_end']=True
  target=s.get('target_text','').strip().lower()
  if action in ('set_speed','speed_up','slow_down') and re.fullmatch(r'(?:the )?(?:(?:highest|maximum|max|top|fastest)(?: possible)? speed|speed|\u6700\u9ad8\u901f\u5ea6|\u6700\u5feb\u901f\u5ea6)',target):
   s['target_text']=''
  if action in ('speed_up','slow_down'):
   soft={'a little','a bit','slightly','gently','\u4e00\u70b9','\u4e00\u70b9\u70b9','\u7a0d\u5fae'}
   if any(c.strip().lower() in soft for c in s.get('constraints',[])):
    s['speed_delta_mps']=1.0
    s['constraints']=[c for c in s['constraints'] if c.strip().lower() not in soft]
  if s.get('trigger')=='now':
   here={'here','right here','at the current location','\u5728\u8fd9\u91cc','\u5728\u8fd9\u91cc (at the current location)'}
   s['constraints']=[c for c in s.get('constraints',[]) if c.strip().lower() not in here]
  if action=='continuous_drive' and s.get('completion_text','').strip().lower() in {'until the road ends','until you reach the end','until the end','to the end','the end','to the end of the road','\u5230\u8def\u5c3d\u5934'}:
   s['completion_text']='' # Native follow-road control already stops at map end.
  if action in ('pull_over','park','reverse','reverse_continuous','go_straight','keep_lane','turn_left','turn_right','u_turn','lane_change_left','lane_change_right') and s.get('completion_text','').strip().lower() in {'stop','and stop','then stop','come to a stop','\u505c\u8f66','\u505c\u4e0b'}:
   s['completion_text']='';s['stop_at_end']=True
  if action=='select_lane' and s.get('lane_number') is None and s.get('lane_reference') in ('leftmost','rightmost'):
   clause=s.get('source_clause','').lower()
   if not re.search(r'\d|second|third|fourth|\u7b2c\u4e94|\u7b2c\u4e8c|\u7b2c\u4e09|\u7b2c\u56db',clause):s['lane_number']=1
 expanded=[]
 for s in p.get('stages',[]):
  count=s.get('lane_number')
  if s['action'] in ('lane_change_left','lane_change_right') and type(count) is int and 1<count<=4:
   for i in range(count):expanded.append({**s,'lane_number':1,'trigger':s['trigger'] if i==0 else 'after_previous','source_clause':s['source_clause']+' (lane '+str(i+1)+'/'+str(count)+')'})
  else:expanded.append(s)
 p['stages']=expanded
 for i,s in enumerate(expanded):
  if i and expanded[i-1]['action']=='u_turn' and s['action']=='go_straight' and s.get('completion_text','').strip().lower() in ('head back','go back','return') and not s.get('target_text') and not s.get('constraints') and s.get('travel_distance_m') is None:
   s['action']='continuous_drive';s['completion_text']=''
 for a,b in zip(expanded,expanded[1:]):
  if a['action'] in ('go_straight','keep_lane') and a.get('travel_distance_m') is not None and b['action']=='stop' and b.get('trigger')=='after_previous' and not any(b.get(k) for k in ('target_text','constraints','completion_text')):
   a['stop_at_end']=True
 return p
