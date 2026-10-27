exec(open(__file__.replace('probe_curve.py','probe_retarget.py')).read().split("for m in scene.topology")[0])
import numpy as np
from engine.geometry import footprint,angle_diff
state=json.loads(Path('historical-project/runs/project-v3/refactor-v33/requests/6e7a06ec-b236-4fce-be11-91fcb63d408b.json').read_text())['request']['state']
a=np.array(state['xy']);h0=state['heading'];target=scene.nodes['L67611'];b=np.array(target.baseline.coords[0]);h1=tangent(target.baseline,b)
u=np.linspace(0,1,160)[:,None];best=(999,None)
for s0 in (3,5,8,10,12,15,18,22,28,35,45,55):
 for s1 in (3,5,8,10,12,15,18,22,28,35,45,55,65,75):
  v0=s0*np.array([math.cos(h0),math.sin(h0)]);v1=s1*np.array([math.cos(h1),math.sin(h1)])
  pts=(2*u**3-3*u**2+1)*a+(u**3-2*u**2+u)*v0+(-2*u**3+3*u**2)*b+(u**3-u**2)*v1
  d=np.gradient(pts,axis=0);dd=np.gradient(d,axis=0);k=np.abs(d[:,0]*dd[:,1]-d[:,1]*dd[:,0])/np.maximum(np.linalg.norm(d,axis=1)**3,1e-8)
  if k.max()<best[0]:best=(k.max(),(s0,s1))
  if k.max()>.2215:continue
  hs=np.arctan2(d[:,1],d[:,0]);inside=all(scene.graph.surface.covers(footprint(p,h,4.8,2)) for p,h in zip(pts,hs))
  print('candidate',s0,s1,k.max(),'inside',inside,'left',max(np.unwrap(hs)-h0),'overshoot',min(np.unwrap(hs))-h1,flush=True)
print('live',a,h0,'target',b,h1,'best',best)

