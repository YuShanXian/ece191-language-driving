"""Find a directed map connection that returns into an opposite-facing lane."""
import heapq
import numpy as np
from shapely.geometry import Point
from trajectory_checks import tangent,angle_diff

def find_uturn(graph,center,start):
 first=graph.nodes[start];remaining=max(0.,first.baseline.length-first.baseline.project(Point(center[:2])))
 queue=[(remaining,[start])];visits=0
 while queue and visits<4000:
  cost,path=heapq.heappop(queue);visits+=1;node=graph.nodes[path[-1]]
  end=np.array(node.baseline.coords[-1])[:2]
  if len(path)>1 and node.kind=='lane' and abs(angle_diff(tangent(node.baseline,end),center[6]))>np.radians(150) and node.baseline.distance(Point(center[:2]))<60:
   return path
  if len(path)>=12 or cost>250:continue
  for key,relation in graph.edges.get(path[-1],{}).items():
   if relation!='forward' or key in path:continue
   nxt=graph.nodes[key];startxy=np.array(nxt.baseline.coords[0])[:2]
   if np.linalg.norm(startxy-end)>3:continue
   heapq.heappush(queue,(cost+nxt.baseline.length,path+[key]))
 return None
