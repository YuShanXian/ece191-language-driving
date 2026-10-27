"""Ground candidate destinations and generate separately identified map supplements."""
import numpy as np
from shapely.geometry import Point
from trajectory_checks import headings,tangent,angle_diff
from instruction_priority_selector import describe,evidence
from instruction_priority_v2 import lane_targets,target_evidence

def destination(points,heading,graph,action):
 angles=headings(points,heading);hits=[]
 for idx in graph.tree.query(Point(points[-1]),predicate='intersects'):
  key=graph.keys[int(idx)];n=graph.nodes[key];h=tangent(n.baseline,points[-1])
  relative=np.degrees(angle_diff(h,heading))
  if abs(angle_diff(angles[-1],h))>np.radians(25):continue
  if action=='go_straight' and abs(relative)>20:continue
  if action=='turn_left' and not 30<=relative<=140:continue
  if action=='turn_right' and not -140<=relative<=-30:continue
  settled=sum(n.polygon.buffer(.15).covers(Point(p)) for p in points[-6:])>=5
  if settled:hits.append({'node':key,'road_heading_change_deg':float(relative),'endpoint_centerline_distance_m':float(n.baseline.distance(Point(points[-1])))})
 return min(hits,key=lambda x:x['endpoint_centerline_distance_m']) if hits else None

def assess(points,center,graph,starts,action,row):
 f=describe(points,float(center[6]),row)
 if action.startswith('lane_change_'):
  targets=lane_targets(graph,starts,action.rsplit('_',1)[1]);target=target_evidence(points,float(center[6]),graph,targets)
  if not target:return None
  f['target']=target
 else:
  if not evidence(f,action):return None
  target=destination(points,float(center[6]),graph,action)
  if not target:return None
  f['target']=target
 f['center_on_road_fraction']=float(np.mean([graph.surface.covers(Point(p)) for p in points]))
 return f

def quintic(center,end,end_heading,acceleration):
 T=6.;p0=np.asarray(center[:2],float);v0=np.asarray(center[7:9],float)
 distance=np.linalg.norm(end-p0);speed=min(max(distance/T,1.),12.)
 vf=speed*np.array([np.cos(end_heading),np.sin(end_heading)])
 a0=np.asarray(acceleration,float)
 c0=p0;c1=v0*T;c2=.5*a0*T*T
 A=np.array([[1,1,1],[3,4,5],[6,12,20]],float)
 rhs=np.array([end-c0-c1-c2,vf*T-c1-2*c2,-2*c2])
 c3,c4,c5=np.linalg.solve(A,rhs);u=np.linspace(0,1,61)[:,None]
 return c0+c1*u+c2*u*u+c3*u**3+c4*u**4+c5*u**5

def supplements(center,graph,starts,action,acceleration):
 h=float(center[6]);rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]])
 targets=lane_targets(graph,starts,action.rsplit('_',1)[1]) if action.startswith('lane_change_') else None
 keys=set().union(*(t['continuation'] for t in targets)) if targets else (set() if targets==[] else set(graph.nodes))
 proposals=[]
 for key in sorted(keys):
  n=graph.nodes[key]
  if n.baseline.length<3:continue
  for fraction in [.25,.5,.75,.95]:
   end=np.array(n.baseline.interpolate(n.baseline.length*fraction).coords[0])[:2]
   local=(end-center[:2])@rot;dist=float(np.linalg.norm(local))
   if not 8<=dist<=70 or local[0]<2:continue
   eh=tangent(n.baseline,end);delta=np.degrees(angle_diff(eh,h))
   if action=='go_straight' and (abs(delta)>15 or abs(local[1])>2):continue
   if action=='turn_left' and not (35<=delta<=125 and local[1]>5):continue
   if action=='turn_right' and not (-125<=delta<=-35 and local[1]<-5):continue
   p=quintic(center,end,eh,acceleration)
   chord=np.linalg.norm(end-center[:2]);length=np.linalg.norm(np.diff(p,axis=0),axis=1).sum()
   if length>2*chord or np.linalg.norm(np.diff(p,axis=0)/.1,axis=1).max()>40:continue
   row={'route':{'matched':False}}
   f=assess(p,center,graph,starts,action,row)
   if f:proposals.append({'points':p,'features':f,'target_node':key,'source':'map_quintic_supplement','mtr_score':None})
 return proposals
