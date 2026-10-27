import numpy as np
from shapely.geometry import Polygon,LineString
from trajectory_checks import RoadGraph,RoadNode
from instruction_priority_v2 import lane_targets,target_evidence
from map_instruction_candidates import quintic,destination
def lane(key,y):
 return RoadNode(key,Polygon([(0,y-1.7),(80,y-1.7),(80,y+1.7),(0,y+1.7)]),LineString([(0,y),(80,y)]),'lane',1,int(y/3.5))
g=RoadGraph([lane('a',0),lane('b',3.5)],{'a':{'b':'left'}})
t=lane_targets(g,['a'],'left');assert len(t)==1
assert not lane_targets(g,['a'],'right')
x=np.linspace(1,31,61);u=np.linspace(0,1,61);change=np.c_[x,3.5*(3*u*u-2*u**3)]
assert target_evidence(change,0,g,t)
drift=np.c_[x,.8*u];assert target_evidence(drift,0,g,t) is None
cross=np.c_[x,7*u];assert target_evidence(cross,0,g,t) is None
center=np.zeros(9);center[:2]=[1,0];center[7]=5
p=quintic(center,np.array([31.,3.5]),0,np.zeros(2))
assert np.allclose(p[0],center[:2]) and np.allclose(p[-1],[31,3.5])
assert np.linalg.norm((p[1]-p[0])/.1-center[7:9])<.1
assert destination(np.c_[x,np.zeros(61)],0,g,'go_straight')
assert destination(np.c_[x,np.zeros(61)],0,g,'turn_left') is None
print('9 grounding and boundary checks passed')
