"""Free-mode U-turn ending on an actual opposite-direction map lane."""
import numpy as np
from scipy.interpolate import CubicSpline
from shapely.geometry import Point
from trajectory_checks import tangent,angle_diff
from centerline_trajectory_planner import CONFIG
from distance_motion_v3 import distance_motion

def generate_to_lane(graph,center,acc):
 start=center[:2].copy();h=float(center[6]);candidates=[]
 def onward(key):
  total=0.;seen=set();queue=[key]
  while queue and len(seen)<100:
   k=queue.pop()
   if k in seen:continue
   seen.add(k);total+=graph.nodes[k].baseline.length
   queue.extend(n for n,r in graph.edges.get(k,{}).items() if r=='forward')
  return total
 for node in graph.nodes.values():
  if node.kind!='lane':continue
  line=node.baseline;pos=line.project(Point(start));d=line.distance(Point(start))
  if d>60 or abs(angle_diff(tangent(line,start),h))<np.radians(145) or line.length-pos<2:continue
  join=min(pos+6,line.length-1.5);end=np.asarray(line.interpolate(join).coords[0])[:2];head=tangent(line,end)
  scale=max(10.,np.linalg.norm(end-start)*1.3);v0=scale*np.array([np.cos(h),np.sin(h)]);v1=scale*np.array([np.cos(head),np.sin(head)])
  u=np.linspace(0,1,160)[:,None]
  bridge=(2*u**3-3*u**2+1)*start+(u**3-2*u**2+u)*v0+(-2*u**3+3*u**2)*end+(u**3-u**2)*v1
  # Extra tangent beyond the stopping point is used only for stable spline derivatives.
  pts=np.vstack([bridge,end+2*np.array([np.cos(head),np.sin(head)])]);s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))]
  if np.any(np.diff(s)<1e-6):continue
  curve=CubicSpline(s,pts);ds=np.arange(0,s[-1],.1);der=curve(ds,1);dd=curve(ds,2);curv=(der[:,0]*dd[:,1]-der[:,1]*dd[:,0])/np.maximum(np.linalg.norm(der,axis=1)**3,1e-8)
  shape={'curve':curve,'length':s[-1],'arc_s':ds,'curvature':curv}
  config=dict(CONFIG);config['cruise_speed_mps']=3.
  try:p,timing=distance_motion(shape,center,acc,float(s[-2]),False,config)
  except ValueError:continue
  body=graph.body_check(p,h,float(center[3]),float(center[4]));steer=float(np.max(np.abs(np.arctan(CONFIG['wheelbase_m']*curv))))
  reachable=onward(node.key)-(pos+6)
  if reachable<20:continue
  candidates.append((False,d,node.key,p,timing,head,body,steer))
 if not candidates:return None
 _,d,key,p,timing,head,body,steer=min(candidates,key=lambda x:x[:3])
 info={'trajectory_source':'free_uturn_to_opposite_map_lane','target':key,'body_check_passed':body['passed'],'max_steering_rad':steer,'heading_change_deg':float(np.degrees(abs(angle_diff(head,h)))),'road_fit':'opposite map lane at endpoint','endpoint_centerline_distance_m':float(graph.nodes[key].baseline.distance(Point(p[-1]))),'reason':'U-turn joins an opposite-direction map lane and continues on its forward connections.','checks_overridden':not body['passed'] or steer>CONFIG['steering_limit_rad']}
 if info['checks_overridden']:info['warning']='Free-mode U-turn joins the opposite lane; the connecting curve may cross road boundaries or exceed steering limits.'
 return p,timing,head,info
