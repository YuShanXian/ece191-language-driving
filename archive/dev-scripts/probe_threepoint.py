import sys,json,pickle,math,time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from shapely.geometry import Point
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parents[1]/'sim'))
from engine.geometry import heading,tangent,angle_diff,footprint
from engine.planner import reverse
from engine.recovery import reverse_clearance
scene=pickle.loads((root/'results/scene1.pkl').read_bytes());state=json.loads((root/'results/user-step8-failed.json').read_text())['request']['state']
def phases(a,h,angles,radius,side):
 out=[];p=np.array(a);yaw=h
 for angle,gear in zip(angles,(1,-1,1)):
  k=side*gear/radius;travel=gear*radius*angle
  d=np.linspace(0,travel,max(3,int(abs(travel)/.2)+1));hs=yaw+k*d
  pts=np.column_stack([p[0]+(np.sin(hs)-math.sin(yaw))/k,p[1]-(np.cos(hs)-math.cos(yaw))/k])
  out.append((pts,hs,gear));p=pts[-1];yaw=hs[-1]
 return out
start=time.perf_counter()
for back in (3,5,8,12,18,25):
 rev=reverse(scene,state,back)
 if not reverse_clearance(rev,scene.graph.surface):continue
 a=rev['points'][-1];h=heading(rev['points'],True)+math.pi
 for key in ('L63380','L63379'):
  line=scene.nodes[key].baseline;at=line.project(Point(a))
  for delta in (0,-2,2,-4,4,-8,8):
   s=max(5,min(line.length-8,at+delta));b=np.array(line.interpolate(s).coords[0]);h1=tangent(line,b)
   for radius in (4.8,5.5,6.5):
    for side in (1,-1):
     def residual(angles):
      p,hs,_=phases(a,h,angles,radius,side)[-1]
      return [*(p[-1]-b),radius*angle_diff(hs[-1],h1)]
     sol=least_squares(residual,[1.25,.65,1.25],bounds=([.15,.15,.15],[1.6,2.8,1.6]),max_nfev=35)
     if np.linalg.norm(sol.fun)>.03:continue
     paths=phases(a,h,sol.x,radius,side)
     if not all(scene.graph.surface.covers(footprint(p,y,4.8,2)) for pts,hs,g in paths for p,y in zip(pts,hs)):continue
     print('FOUND',back,key,s,radius,side,sol.x,'ms',(time.perf_counter()-start)*1000,flush=True)
     (root/'results/threepoint-witness.json').write_text(json.dumps(dict(back=back,target=key,offset=s,radius=radius,side=side,angles=sol.x.tolist(),phases=[dict(points=p.tolist(),headings=h.tolist(),gear=g) for p,h,g in paths]),indent=2))
     sys.exit(0)
print('NO WITNESS')
