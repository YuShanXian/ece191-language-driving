"""Distance-target speed profile with exact endpoint and optional zero end speed."""
import numpy as np

def distance_motion(shape,center,acc,distance,stop,config):
 if distance>shape['length']-1:raise ValueError(f'Requested {distance:.1f} m, but the selected mapped road has only {max(0., shape["length"]-1):.1f} m available from the current position')
 dt=config['dt'];v0=float(np.linalg.norm(center[7:9]));a0=float(np.dot(acc,[np.cos(center[6]),np.sin(center[6])]))
 vend=0. if stop else min(config['cruise_speed_mps'],max(2.,v0))
 for steps in range(max(10,int(distance/10/dt)),max(1201,min(6001,int(3*distance/max(.25,config["cruise_speed_mps"])/dt)+1))):
  T=steps*dt;c=np.zeros(6);c[1]=v0;c[2]=a0/2
  c[3:]=np.linalg.solve([[T**3,T**4,T**5],[3*T*T,4*T**3,5*T**4],[6*T,12*T*T,20*T**3]],[distance-v0*T-a0*T*T/2,vend-v0-a0*T,-a0])
  t=np.arange(steps+1)*dt;s=sum(c[i]*t**i for i in range(6));v=sum(i*c[i]*t**(i-1) for i in range(1,6));a=sum(i*(i-1)*c[i]*t**(i-2) for i in range(2,6));j=sum(i*(i-1)*(i-2)*c[i]*t**(i-3) for i in range(3,6))
  curvature=np.abs(np.interp(s,shape['arc_s'],shape['curvature']))
  if v.min()<-1e-6 or v.max()>max(v0,config['cruise_speed_mps'])+.01 or a.max()>2 or a.min()<-2.5 or np.abs(j).max()>4 or np.max(v*v*curvature)>2.5:continue
  s=np.clip(s,0,distance);s[-1]=distance;v=np.maximum(v,0);v[-1]=vend
  points=shape['curve'](s);points[0]=center[:2]
  return points,{'speed_mps':v.tolist(),'longitudinal_accel_mps2':a.tolist(),'progress_m':s.tolist(),'horizon_s':T}
 raise ValueError('No feasible distance-target speed profile from current speed')
