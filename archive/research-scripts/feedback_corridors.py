"""Feedback-guided map corridors. Explicit development-set target specifications."""
import numpy as np
from shapely.geometry import LineString,Point
from scipy.interpolate import CubicSpline
from trajectory_checks import tangent,angle_diff,headings

def guide_for(graph,keys,center):
 points=[]
 for i,key in enumerate(keys):
  line=graph.nodes[key].baseline
  start=line.project(Point(center[:2])) if i==0 else 0.
  for d in np.arange(start,line.length+.25,.5):
   p=np.asarray(line.interpolate(min(d,line.length)).coords[0])[:2]
   if not points or np.linalg.norm(p-points[-1])>.05:points.append(p)
  p=np.asarray(line.coords[-1])[:2]
  if np.linalg.norm(p-points[-1])>.05:points.append(p)
 return LineString(points)

def curve_on_guide(guide,center,distance,duration=6.):
 distance=min(distance,guide.length-.1)
 knots=np.unique(np.r_[0,np.arange(3,distance,2),distance])
 pts=np.array([guide.interpolate(float(s)).coords[0] for s in knots])[:,:2]
 offset=np.asarray(center[:2])-pts[0];u=np.clip(knots/12.,0,1);blend=1-(3*u*u-2*u*u*u);pts+=blend[:,None]*offset;pts[0]=center[:2]
 endh=tangent(guide,pts[-1]);h=float(center[6])
 spline=CubicSpline(knots,pts,bc_type=((1,np.array([np.cos(h),np.sin(h)])),(1,np.array([np.cos(endh),np.sin(endh)]))))
 # Time law preserves start speed; nonnegative derivatives required.
 v0=float(np.linalg.norm(center[7:9]));vf=max(1.,distance/duration)
 from scipy.interpolate import CubicHermiteSpline
 law=CubicHermiteSpline([0.,duration],[0.,distance],[v0,vf]);t=np.linspace(0,duration,int(round(duration*10))+1);s=law(t)
 if np.min(law(t,1))<-.01 or s.min()<-.01:return None
 return spline(s)

def corridor_evidence(points,center,guide,action,minimum_progress):
 angles=headings(points,float(center[6]));progress=np.array([guide.project(Point(p)) for p in points]);dist=np.array([guide.distance(Point(p)) for p in points]);delta=np.array([abs(np.degrees(angle_diff(h,tangent(guide,p)))) for p,h in zip(points,angles)])
 # Allow the approach lane crossing but require actual settling on intended corridor.
 if progress[-1]<minimum_progress or np.max(dist[-6:])>1.6 or np.max(delta[-6:])>25 or np.any(np.diff(progress)<-.75):return None
 settled=dist[progress>=12.]
 if len(settled) and np.max(settled)>3.6:return None
 enddelta=float(np.degrees(angle_diff(angles[-1],center[6])))
 if action=='turn_left' and enddelta<55:return None
 if action=='turn_right' and enddelta>-50:return None
 return {'end_progress_m':float(progress[-1]),'max_centerline_distance_m':float(dist.max()),'end_centerline_distance_m':float(dist[-1]),'ending_heading_change_deg':enddelta}



