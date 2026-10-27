import sys
sys.path.insert(0,'historical-project/scripts')
from free_navigation_v8 import context
from navigation_turn_v15 import locate
from shapely.geometry import Point
from trajectory_checks import tangent,angle_diff
import numpy as np,math
g,c,rot=context(7);p=c[:2];h=c[6];key=locate(g,p,h);print('CURRENT',key)
for n in g.nodes.values():
 if n.baseline.distance(Point(p))<12:
  print(n.key,n.kind,'group',n.lane_group,'distance',round(n.baseline.distance(Point(p)),2),'length',round(n.baseline.length,1),'angle',round(math.degrees(angle_diff(tangent(n.baseline,np.array(n.baseline.coords[-1])[:2]),h)),1),'edges',g.edges.get(n.key))
