"""Time a map polyline at requested cruise speed, slowing for bends and stops."""
import numpy as np
def sample(points,target,initial,stop=False,dt=.1,end_speed=None):
 p=np.asarray(points,float)
 # Remove tiny initial backtracking introduced by the old trajectory join.
 # Otherwise arc-length timing spends a whole frame moving out and back.
 if len(p)>3:
  direction=p[1]-p[0];norm=np.linalg.norm(direction)
  if norm>1e-6:
   direction/=norm;keep=[p[0]];progress=0.
   for point in p[1:]:
    forward=float((point-p[0])@direction)
    if np.linalg.norm(point-p[0])<5 and forward<progress-1e-5:continue
    keep.append(point);progress=max(progress,forward)
   p=np.asarray(keep)
 arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
 s=np.linspace(0,arc[-1],max(3,int(arc[-1]/.4)+1));q=np.column_stack([np.interp(s,arc,p[:,j]) for j in range(2)])
 heading=np.unwrap(np.arctan2(np.gradient(q[:,1]),np.gradient(q[:,0])));curv=np.abs(np.gradient(heading,s));limit=np.minimum(max(.1,target),np.sqrt(2.5/np.maximum(curv,.0001)));v=limit.copy();v[0]=min(max(0,initial),limit[0])
 if stop:v[-1]=0
 elif end_speed is not None:v[-1]=min(v[-1],end_speed)
 for i in range(1,len(s)):v[i]=min(v[i],np.sqrt(v[i-1]**2+3*(s[i]-s[i-1])))
 for i in range(len(s)-2,-1,-1):v[i]=min(v[i],np.sqrt(v[i+1]**2+5*(s[i+1]-s[i])))
 # A new command must not instantly lower the actual vehicle speed.
 v[0]=max(0,float(initial))
 for i in range(1,len(s)):
  ds=s[i]-s[i-1];v[i]=max(v[i],np.sqrt(max(0,v[i-1]**2-5*ds)))
 times=np.r_[0,np.cumsum(2*np.diff(s)/np.maximum(.05,v[:-1]+v[1:]))];n=max(1,int(np.ceil(times[-1]/dt)));t=np.linspace(0,times[-1],n+1);distance=np.interp(t,times,s);xy=np.column_stack([np.interp(distance,arc,p[:,j]) for j in range(2)]);speed=np.r_[np.linalg.norm(np.diff(xy,axis=0),axis=1)/dt,0 if stop else v[-1]]
 return xy,speed
