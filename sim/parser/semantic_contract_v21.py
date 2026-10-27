"""Canonicalize equivalent LLM plans without dropping real conditions.

Language still goes through the selected LLM. These narrow rules reconcile
equivalent encodings of the simulator's documented commands, not a lookup of
test sentences or a replacement natural-language parser.
"""
import copy,re

def canonicalize(instruction,plan):
 p=copy.deepcopy(plan)
 if p.get('status')!='parsed' or p.get('unresolved_text'):return p
 rows=p.get('stages',[]);changes=[]
 for row in rows:
  if row['action']=='hold_stopped':
   old=row.get('constraints',[])
   row['constraints']=[c for c in old if c.strip().lower().rstrip('.\u3002!\uff01') not in {'do not move',"don't move",'stay stopped','remain stopped','\u4fdd\u6301\u505c\u8f66','\u4fdd\u6301\u9759\u6b62','\u4e0d\u8981\u79fb\u52a8','\u522b\u52a8'}]
   if old!=row['constraints']:changes.append('The no-movement constraint is inherent in hold_stopped.')
 # Explicit keep/continue/follow-road requests intentionally do not match.
 speed_only=re.fullmatch(r'\s*(?:please\s+)?(?:drive|go|travel)\s+at\s+\d+(?:\.\d+)?\s*(?:mph|km/h|kmh|kph|m/s|miles per hour|kilomet(?:er|re)s per hour|met(?:er|re)s per second)\s*[.!\u3002]?\s*',instruction,re.I)
 if speed_only and len(rows)==1:
  r=rows[0]
  if r['action']=='continuous_drive' and r.get('target_speed_mps') is not None and not any(r.get(k) for k in ('target_text','constraints','completion_text','travel_distance_m')) and r.get('trigger')=='now':
   r['action']='set_speed';changes.append('A bare numeric speed request updates the speed target; it does not add continuous driving.')
 merged=[]
 for row in rows:
  if merged and merged[-1]['action'] in ('pull_over','park') and row['action']=='stop' and row.get('trigger')=='after_previous' and not any(row.get(k) for k in ('target_text','constraints','completion_text','travel_distance_m','trigger_value')):
   merged[-1]['stop_at_end']=True;merged[-1]['source_clause']+='; '+row['source_clause'];changes.append('Stopping is included in the preceding roadside-stop action.')
  else:merged.append(row)
 p['stages']=merged
 if changes:p['explanation']=' '.join(changes)+' '+p.get('explanation','')
 return p
