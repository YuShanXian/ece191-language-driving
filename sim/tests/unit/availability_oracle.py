"""Test-only geometric witnesses. Never call the production maneuver planner.

No witness means UNRESOLVED, not impossible. A waiting response is not success.
"""
import math
import numpy as np
from shapely.geometry import Point,LineString
from engine.geometry import footprint,arc,tangent,angle_diff

def classify(scene, request):
 state=request['state'];action=request['stage']['action'];xy=np.array(state['xy']);h=state['heading']
 point=Point(xy);left=np.array([-math.sin(h),math.cos(h)])
 nearby=[]
 for i in scene.tree.query(point.buffer(6),predicate='intersects'):
  n=scene.nodes[scene.keys[int(i)]]
  if n.kind!='lane':continue
  at=n.baseline.project(point);p=n.baseline.interpolate(at);angle=angle_diff(tangent(n.baseline,p),h)
  nearby.append((n,at,np.array(p.coords[0]),angle))
 if action in ('lane_change_left','lane_change_right'):
  side=1 if action.endswith('left') else -1
  candidates=[(n,at,p,a) for n,at,p,a in nearby if 1.3<float((p-xy)@left)*side<5.5]
  aligned=[x for x in candidates if abs(x[3])<math.radians(15)]
  source=min(nearby,key=lambda x:np.linalg.norm(x[2]-xy)+abs(x[3])*3,default=None)
  if source:
   sn,sa,_,_=source
   if sn.baseline.length-sa>=26:
    for n,at,p,a in aligned:
     if n.baseline.length-at<27:continue
     u=np.linspace(0,1,101);base=np.array([sn.baseline.interpolate(sa+25*x).coords[0] for x in u])
     dest=np.array([n.baseline.interpolate(n.baseline.project(Point(x))).coords[0] for x in base])
     blend=10*u**3-15*u**4+6*u**5;curve=base+(dest-base)*blend[:,None]
     curve+=(xy-curve[0])*(1-blend[:,None]);d=np.gradient(curve,axis=0);hs=np.arctan2(d[:,1],d[:,0])
     dd=np.gradient(d,axis=0);k=np.abs(d[:,0]*dd[:,1]-d[:,1]*dd[:,0])/np.maximum(np.linalg.norm(d,axis=1)**3,1e-8)
     if k.max()<.22 and all(scene.graph.surface.covers(footprint(p,h,4.8,2)) for p,h in zip(curve,hs)):
      return {'classification':'feasible_witness','target':n.key,'method':'independent_adjacent_baselines','points':curve.tolist()}
  if candidates and not aligned and all(abs(x[3])>math.radians(150) for x in candidates):
   return {'classification':'opposing_lane_only','lanes':[x[0].key for x in candidates]}
 if action=='reverse':
  hist=np.array(state.get('history',[]));length=arc(hist)[-1] if len(hist)>1 else 0
  if length+.15<(request['stage'].get('travel_distance_m') or 10):
   return {'classification':'insufficient_recorded_history','length_m':float(length)}
 if action=='u_turn':
  # Independent catalogue of symmetric F/R/F primitives; unlike production,
  # no fitted target, optimizer, topology adjacency, or generated connectors.
  hist=np.array(state.get('history',[]));hist=np.vstack([hist,xy]) if len(hist) else np.array([xy])
  ds=arc(hist);total=ds[-1]
  for back in (0,3,8,15):
   if total<back:continue
   a=np.array([np.interp(total-back,ds,hist[:,i]) for i in (0,1)])
   before=np.array([np.interp(max(0,total-back-.3),ds,hist[:,i]) for i in (0,1)])
   yaw=math.atan2(*(a-before)[::-1]) if back else h
   for radius in (4.8,5.5,6.5):
    for alpha in (.7,.9,1.1,1.3,1.45):
     for side in (1,-1):
      p=a.copy();angle=yaw;pieces=[];angles=[]
      for turn,gear in zip((alpha,math.pi-2*alpha,alpha),(1,-1,1)):
       theta=np.linspace(angle,angle+side*turn,max(4,int(turn*radius/.2)));k=side*gear/radius
       pts=np.column_stack([p[0]+(np.sin(theta)-math.sin(angle))/k,p[1]-(np.cos(theta)-math.cos(angle))/k])
       pieces.extend(pts);angles.extend(theta);p=pts[-1];angle=theta[-1]
      exits=[]
      for i in scene.tree.query(Point(p).buffer(.15),predicate='intersects'):
       n=scene.nodes[scene.keys[int(i)]]
       if n.kind=='lane' and abs(angle_diff(tangent(n.baseline,p),angle))<.08:exits.append(n.key)
      if exits and all(scene.graph.surface.covers(footprint(p,h,4.8,2)) for p,h in zip(pieces,angles)):
       # A positive witness must also have a valid retreat, if one is used.
       retreat=hist[ds>=total-back] if back else np.array([xy])
       if back and not all(scene.graph.surface.covers(footprint(p,yaw,4.8,2)) for p in retreat):continue
       return {'classification':'feasible_witness','target':exits[0],'method':'independent_symmetric_three_point','reverse_m':back,'points':np.asarray(pieces).tolist()}
 return {'classification':'unresolved','reason':'No independent witness; not counted as successful or impossible'}
