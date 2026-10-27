"""Automatic navigation road selection. Pure map/state/text inputs; no scene or review IDs."""
import numpy as np
from shapely.geometry import Point
from trajectory_checks import tangent,angle_diff
from mtr_project.language import parse_instruction

def select_road(graph,center,instruction):
 parsed=parse_instruction(instruction)
 if parsed['status']!='parsed' or len(parsed['stages'])!=1 or parsed['stages'][0]['trigger']['kind']!='now':
  return {'status':'unsupported_instruction','parsed':parsed}
 action=parsed['stages'][0]['action'];h=float(center[6]);pos=np.asarray(center[:2]);f=np.array([np.cos(h),np.sin(h)]);l=np.array([-np.sin(h),np.cos(h)]);p=Point(pos)
 approaches=[]
 for k,n in graph.nodes.items():
  if n.kind!='lane':continue
  q=np.asarray(n.baseline.interpolate(n.baseline.project(p)).coords[0])[:2];d=q-pos
  angle=float(np.degrees(angle_diff(tangent(n.baseline,q),h)))
  # Adjacent approaches must be nearby, parallel and point in our direction.
  if abs(float(d@f))<=6 and abs(float(d@l))<=12 and abs(angle)<=25:
   approaches.append({'key':k,'lateral_m':float(d@l),'distance_m':float(np.linalg.norm(d)),'angle_deg':angle})
 if not approaches:return {'status':'no_approach','action':action}
 current=min(approaches,key=lambda a:a['distance_m']);branches=[]
 for a in approaches:
  line=graph.nodes[a['key']].baseline;remaining=line.length-line.project(p)
  queue=[([a['key']],remaining)]
  while queue:
   path,length=queue.pop(0);k=path[-1];node=graph.nodes[k];line=node.baseline
   end=np.asarray(line.coords[-1])[:2];rel=end-pos;angle=float(np.degrees(angle_diff(tangent(line,end),h)))
   if node.kind=='connector':
    branches.append({'approach':a['key'],'path':path,'target':k,'lateral_m':a['lateral_m'],'exit_angle_deg':angle,'length_m':float(length),'end_forward_m':float(rel@f),'end_left_m':float(rel@l),'entry_distance_m':float(length-line.length)})
   # Search onward only through gentle branches; do not turn at a second intersection after a turn.
   if len(path)>=6 or length>100 or (node.kind=='connector' and abs(angle)>40):continue
   for nxt,relation in graph.edges.get(k,{}).items():
    if relation=='forward' and nxt not in path:
     queue.append((path+[nxt],length+graph.nodes[nxt].baseline.length))
 if not branches:return {'status':'no_branch','action':action,'approaches':approaches}
 def continuity(b):
  exits=[graph.nodes[k].lane_index for k,r in graph.edges.get(b['target'],{}).items() if r=='forward' and graph.nodes[k].lane_index is not None]
  index=graph.nodes[b['approach']].lane_index
  return min([abs(x-index) for x in exits],default=99)
 def straight(options):
  nearest=min(b['entry_distance_m'] for b in options)
  options=[b for b in options if b['entry_distance_m']<=nearest+12]
  gentle=[b for b in options if abs(b['exit_angle_deg'])<=30 and b['end_forward_m']>0]
  if gentle:return min(gentle,key=lambda b:(abs(b['lateral_m']-current['lateral_m']),abs(b['end_left_m'])+.1*abs(b['exit_angle_deg']),b['length_m'])),'forward_road'
  own=[b for b in options if b['approach']==current['key']] or options
  return min(own,key=lambda b:(continuity(b),abs(b['exit_angle_deg']),b['length_m'])),'follow_road_fallback'
 selected,reason=straight(branches)
 if action in ('turn_left','turn_right'):
  sign=1 if action=='turn_left' else -1
  options=[b for b in branches if 40<=sign*b['exit_angle_deg']<=120 and b['end_forward_m']>0 and b['entry_distance_m']<=60 and sign*b['end_left_m']>0]
  if options:
   selected=min(options,key=lambda b:(abs(b['lateral_m']-current['lateral_m']),continuity(b),b['length_m']));reason='requested_turn'
  else:reason='no_requested_turn_continue_road'
 elif action in ('lane_change_left','lane_change_right'):
  sign=1 if action=='lane_change_left' else -1
  # Compare onward lanes, not approach lanes that may be turn-only.
  base=selected
  onward=[b for b in branches if b['approach']==base['approach'] and b['path'][:len(base['path'])]==base['path'] and abs(b['exit_angle_deg']-base['exit_angle_deg'])<20]
  if onward and abs(base['exit_angle_deg'])<=30 and base['end_forward_m']<25:
   far=max(b['end_forward_m'] for b in onward)
   farther=[b for b in onward if b['end_forward_m']>=far-8]
   base=min(farther,key=lambda b:abs(b['end_left_m']-selected['end_left_m']))
  theta=np.radians(base['exit_angle_deg']);normal=np.array([-np.sin(theta),np.cos(theta)])
  options=[]
  for b in branches:
   delta=np.array([b['end_forward_m']-base['end_forward_m'],b['end_left_m']-base['end_left_m']]);side=float(delta@normal)
   longitudinal=float(contact-removed([np.cos(theta),np.sin(theta)]))
   if 2<sign*side<7 and abs(longitudinal)<12 and abs(b['exit_angle_deg']-base['exit_angle_deg'])<20:
    options.append((abs(side),abs(b['lateral_m']-current['lateral_m']),b['length_m'],b))
  if abs(base['exit_angle_deg'])>30:
   same=[o for o in options if o[3]['approach']==current['key']]
   if same:options=same
   else:
    neighbors=[a for a in approaches if sign*(a['lateral_m']-current['lateral_m'])>2]
    if neighbors:
     nearest=min(neighbors,key=lambda a:abs(a['lateral_m']-current['lateral_m']))
     nearbranches=[b for b in branches if b['approach']==nearest['key']]
     if nearbranches:
      b,_=straight(nearbranches);options=[(0,0,0,b)]
  if options:selected=min(options,key=lambda t:t[:3])[3];reason='adjacent_onward_lane'
  else:selected=base;reason='no_adjacent_onward_lane_continue_road'
 elif action not in ('go_straight','keep_lane'):
  return {'status':'unsupported_action','action':action}
 next_lanes=[k for k,r in graph.edges.get(selected['target'],{}).items() if r=='forward']
 selected=dict(selected)
 if len(next_lanes)==1:selected['path']=selected['path']+next_lanes
 return {'status':'selected','action':action,'selected':selected,'reason':reason,'current':current,'approaches':approaches,'branches':branches}
