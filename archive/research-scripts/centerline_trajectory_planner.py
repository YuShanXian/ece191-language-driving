"""Deterministic centerline planner: geometry first, then curvature-aware speed.
Inputs are selected map roads and current/past vehicle state. No MTR candidates or labels.
Offline prototype; constant-velocity collision checks are diagnostics, not avoidance.
"""
import numpy as np
from scipy.interpolate import CubicSpline
from shapely.geometry import Point,LineString
from trajectory_checks import tangent

CONFIG={'horizon_s':12.,'dt':.1,'cruise_speed_mps':8.,'lateral_accel_mps2':1.8,'envelope_brake_mps2':.8,'stop_margin_m':5.,'accel_mps2':1.5,'brake_mps2':2.5,'jerk_mps3':2.,'join_distances_m':[8.,12.,18.,25.,35.],'wheelbase_m':3.089,'steering_limit_rad':.6}

def road_guide(graph,keys,center):
 pts=[]
 for i,key in enumerate(keys):
  line=graph.nodes[key].baseline;start=line.project(Point(center[:2])) if i==0 else 0.
  for dist in np.r_[np.arange(start,line.length,.5),line.length]:
   p=np.asarray(line.interpolate(float(dist)).coords[0])[:2]
   if not pts or np.linalg.norm(p-pts[-1])>.05:pts.append(p)
 if len(pts)<4:raise ValueError('insufficient map geometry')
 pts=np.asarray(pts);s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))]
 return LineString(pts),CubicSpline(s,pts),s[-1]

def geometry(graph,keys,center,join):
 guide,gs,total=road_guide(graph,keys,center);join=min(join,total-1)
 if join<2:raise ValueError('map corridor too short')
 end=gs(join);der=gs(join,1);der/=max(np.linalg.norm(der),1e-8);h=center[6];start=np.asarray(center[:2]);scale=max(join,np.linalg.norm(end-start));v0=scale*np.array([np.cos(h),np.sin(h)]);v1=scale*der
 # Quintic position curve matches initial heading and joins map position/tangent/curvature.
 d2=gs(join,2)*scale**2;coef=np.zeros((6,2));coef[0]=start;coef[1]=v0
 matrix=np.array([[1,1,1],[3,4,5],[6,12,20]],float);coef[3:]=np.linalg.solve(matrix,np.array([end-start-v0,v1-v0,d2]))
 u=np.linspace(0,1,max(50,int(scale*5)));bridge=sum(u[:,None]**i*coef[i] for i in range(6));tail=gs(np.arange(join+.2,total,.2));pts=np.vstack([bridge,tail,gs(total)])
 lengths=np.linalg.norm(np.diff(pts,axis=0),axis=1);pts=pts[np.r_[True,lengths>.001]];s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))];curve=CubicSpline(s,pts);ds=np.arange(0,s[-1],.2);d=curve(ds,1);dd=curve(ds,2);curv=(d[:,0]*dd[:,1]-d[:,1]*dd[:,0])/np.maximum(np.linalg.norm(d,axis=1)**3,1e-6)
 return {'guide':guide,'curve':curve,'arc_s':ds,'curvature':curv,'length':float(s[-1]),'join_m':float(join),'geometry':curve(ds),'bridge_length_m':float(np.linalg.norm(np.diff(bridge,axis=0),axis=1).sum())}

def time_parameterize(shape,center,initial_acceleration,config=CONFIG):
 ds=shape['arc_s'];k=np.abs(shape['curvature']);limit=np.minimum(config['cruise_speed_mps'],np.sqrt(config['lateral_accel_mps2']/np.maximum(k,1e-5)))
 limit=np.minimum(limit,np.sqrt(2*config['envelope_brake_mps2']*np.maximum(shape['length']-ds-config['stop_margin_m'],0)))
 for i in range(len(ds)-2,-1,-1):limit[i]=min(limit[i],np.sqrt(limit[i+1]**2+2*config['envelope_brake_mps2']*(ds[i+1]-ds[i])))
 dt=config['dt'];v=float(np.linalg.norm(center[7:9]));a=float(np.dot(initial_acceleration,[np.cos(center[6]),np.sin(center[6])]))
 distance=0.;positions=[np.asarray(center[:2])];speeds=[v];accels=[a];progress=[0.];infeasible=v>limit[0]+.5
 for _ in range(round(config['horizon_s']/dt)):
  desired=float(np.interp(min(distance+max(v*1.,2.),ds[-1]),ds,limit));command=np.clip((desired-v)/.5,-config['brake_mps2'],config['accel_mps2']);a=float(np.clip(command,a-config['jerk_mps3']*dt,a+config['jerk_mps3']*dt));vn=max(0.,v+a*dt);distance=min(shape['length'],distance+(v+vn)*.5*dt)
  if distance>=shape['length']:vn=0.
  positions.append(shape['curve'](distance));speeds.append(vn);accels.append(a);progress.append(distance);v=vn
 p=np.asarray(positions)
 return p,{'speed_mps':speeds,'longitudinal_accel_mps2':accels,'progress_m':progress,'initial_speed_above_braking_envelope':bool(infeasible),'peak_lateral_accel_mps2':float(np.max(np.asarray(speeds)**2*np.abs(np.interp(progress,ds,shape['curvature'])))),'horizon_s':config['horizon_s']}

def path_metrics(points,guide,initial_velocity,initial_acceleration):
 from trajectory_checks import motion_check
 p=np.asarray(points);dist=np.array([guide.distance(Point(x)) for x in p]);motion=motion_check(p,initial_velocity,initial_acceleration=initial_acceleration)
 return {'mean_centerline_distance_m':float(dist.mean()),'last_second_centerline_distance_m':float(dist[-10:].mean()),'max_centerline_distance_m':float(dist.max()),'motion':motion}
