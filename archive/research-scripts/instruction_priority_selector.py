"""Offline instruction-priority selection. Risk findings annotate, never veto.
No control output. No recorded future, reviewer verdict, scene ID or video used to select.
"""
import numpy as np
from trajectory_checks import headings,angle_diff

def describe(points,heading,row):
 p=np.asarray(points);a=headings(p,heading)
 rot=np.array([[np.cos(heading),-np.sin(heading)],[np.sin(heading),np.cos(heading)]])
 q=(p-p[0])@rot
 delta=float(np.degrees(angle_diff(float(np.median(np.unwrap(a)[-6:])),heading)))
 forward=float(q[-1,0]);left=float(q[-1,1]);distance=float(np.linalg.norm(p[-1]-p[0]))
 route=row['route'];changes=route.get('lane_changes',[]) if route.get('matched') else []
 return dict(heading_change_deg=delta,forward_m=forward,left_m=left,displacement_m=distance,
 lane_changes=changes,road_matched=bool(route.get('matched')))

def evidence(f,action):
 d=f['heading_change_deg'];x=f['forward_m'];y=f['left_m']
 if f['displacement_m']<3:return None
 if action in ('turn_left','turn_right'):
  sign=1 if action=='turn_left' else -1
  if 25<=sign*d<=150 and sign*y>=1.5:
   return 'road_and_geometry' if f['road_matched'] else 'geometry_only'
 if action=='go_straight':
  if x>=5 and abs(d)<=20 and abs(y)<=2.0:return 'road_and_geometry' if f['road_matched'] else 'geometry_only'
 if action.startswith('lane_change_'):
  sign=1 if action.endswith('left') else -1
  events=f['lane_changes']
  if any(e['action']==action for e in events) and not any(e['action']!=action for e in events):
   return 'map_lane_transition'
  # A lateral displacement is only a hypothesis, never a confirmed lane change.
  if x>=5 and 2<=sign*y<=8 and abs(d)<=20:return 'lateral_motion_only'
 return None

def select_priority(rows,trajectories,center,action):
 scored=[]
 for row,xy in zip(rows,trajectories):
  p=np.vstack([center[:2],xy]);f=describe(p,float(center[6]),row);ev=evidence(f,action)
  if ev is None:continue
  # Prefer a map-supported action, then MTR score. Safety findings are NOT ranking inputs.
  tier=2 if ev in ('road_and_geometry','map_lane_transition') else 1
  scored.append((tier,float(row['score']),row,f,ev))
 if not scored:return {'candidate':None,'status':'no_action_candidate','matching_candidates':[]}
 _,_,row,f,ev=max(scored,key=lambda t:(t[0],t[1],-t[2]['candidate']))
 return {'candidate':row['candidate'],'status':'selected_for_offline_review',
 'evidence':ev,'features':f,'model_score':row['score'],
 'risk_flags':list(row['rejected_by']),'passes_existing_checks':row['passes_current_checks'],
 'unassessed':['traffic_light','lane_marking_legality','interactive_traffic_response'],
 'matching_candidates':[r[2]['candidate'] for r in scored],
 'scope':'Offline instruction priority; matching is not validated compliance or safety.'}
