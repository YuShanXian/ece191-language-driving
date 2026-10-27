import json,numpy as np
from shapely.geometry import Point
from trajectory_checks import headings,tangent,angle_diff
from instruction_priority_v2 import forward_nodes

def target_match(points,heading,graph,targets):
 angles=headings(points,heading);evidence=[]
 for key in targets:
  n=graph.nodes[key];progress=np.array([n.baseline.project(Point(p)) for p in points]);dist=np.array([n.baseline.distance(Point(p)) for p in points]);aligned=np.array([abs(np.degrees(angle_diff(h,tangent(n.baseline,p))))<30 for p,h in zip(points,angles)])
  inside=np.array([n.polygon.buffer(.05).covers(Point(p)) for p in points]);hit=inside&aligned&(dist<=1.6)
  best=0;streak=0;hitprogress=[]
  for i,b in enumerate(hit):
   streak=streak+1 if b else 0;best=max(best,streak)
   if b:hitprogress.append(progress[i])
  span=float(max(hitprogress)-min(hitprogress)) if hitprogress else 0
  required=min(4.,n.baseline.length*.4)
  branch=forward_nodes(graph,key,3)
  endok=all(any(graph.nodes[k].polygon.buffer(.05).covers(Point(p)) and abs(np.degrees(angle_diff(h,tangent(graph.nodes[k].baseline,p))))<35 for k in branch) for p,h in zip(points[-6:],angles[-6:]))
  reached=best>=6 and span>=required and endok
  evidence.append({'target':key,'matched':bool(reached),'consecutive_aligned_steps':best,'progress_on_target_m':span,'required_progress_m':required,'mean_target_distance_m':float(np.mean(dist[hit])) if hit.any() else None,'end_on_target_branch':bool(endok),'closest_distance_m':float(dist.min())})
 winners=[e for e in evidence if e['matched']]
 return {'matched':bool(winners),'target':min(winners,key=lambda e:e['mean_target_distance_m'])['target'] if winners else None,'evidence':evidence}
