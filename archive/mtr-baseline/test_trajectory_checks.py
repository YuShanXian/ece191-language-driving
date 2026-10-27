import unittest
import numpy as np
from shapely.geometry import box,LineString
from trajectory_checks import RoadGraph,RoadNode,motion_check,collision_check,headings
from refine_candidate_paths import refine

def fixture():
    nodes=[]
    for key,x0,x1,y,kind in [('a',0,30,0,'lane'),('b',0,30,3.5,'lane'),
                            ('c',30,40,0,'connector'),('d',30,40,3.5,'connector'),
                            ('e',40,100,0,'lane'),('f',40,100,3.5,'lane')]:
        nodes.append(RoadNode(key,box(x0,y-1.75,x1,y+1.75),LineString([(x0,y),(x1,y)]),kind))
    edges={'a':{'b':'left','c':'forward'},'b':{'a':'right','d':'forward'},'c':{'e':'forward'},'d':{'f':'forward'}}
    return RoadGraph(nodes,edges)

class Checks(unittest.TestCase):
    def test_overlapping_junction_cannot_choose_new_start_lane(self):
        shared=box(0,-2,30,2);baseline=LineString([(0,0),(30,0)])
        nodes=[RoadNode('a',shared,baseline,'connector'),RoadNode('b',shared,baseline,'connector'),
               RoadNode('c',box(30,-2,60,2),LineString([(30,0),(60,0)]),'lane')]
        g=RoadGraph(nodes,{'b':{'c':'forward'}});p=np.c_[np.linspace(5,50,61),np.zeros(61)]
        self.assertTrue(g.match(p,0)['matched'])
        self.assertFalse(g.match(p,0,start_nodes={'a'})['matched'])
    def test_refinement_preserves_constant_speed(self):
        p=np.c_[np.arange(61),np.zeros(61)]
        q,report=refine(p,[10,0])
        self.assertTrue(np.allclose(q,p,atol=1e-8));self.assertTrue(report['within_deviation_bound'])
    def test_acceleration_boundary_uses_past_motion(self):
        p=np.c_[np.arange(61),np.zeros(61)]
        v=np.array([10.,0.]);a=np.array([0.,2.])
        q,_=refine(p,v,initial_acceleration=a)
        interval_v=np.diff(q[:3],axis=0)/.1
        accelerations=np.diff(np.vstack([v,interval_v]),axis=0)/.1
        self.assertTrue(np.allclose(accelerations,np.tile(a,(2,1))))
    def test_zero_acceleration_preserves_constant_speed(self):
        p=np.c_[np.arange(61),np.zeros(61)]
        q,_=refine(p,[10.,0.],initial_acceleration=[0.,0.])
        self.assertTrue(np.allclose(q,p,atol=1e-8))
    def test_refinement_is_not_unbounded_repair(self):
        p=np.zeros((61,2));q,report=refine(p,[40,0])
        self.assertFalse(report['within_deviation_bound'])
        self.assertTrue(np.allclose((q[1]-q[0])/.1,[40,0]))
    def test_lane_change_completion_after_connector(self):
        x=np.arange(5,66);y=np.clip((x-10)/15,0,1)*3.5
        p=np.c_[x,y];g=fixture();m=g.match(p,0);g.settled_lane_changes(m,p,0,4,2)
        self.assertTrue(m['lane_changes'][0]['settled_for_last_half_second'])
    def test_stationary_jitter_does_not_rotate_body(self):
        p=np.c_[np.tile([0.,.03],31)[:61],np.zeros(61)]
        self.assertTrue(np.allclose(headings(p,0),0))
    def test_turn_heading_tracks_curve_without_trailing_lag(self):
        angles=np.arange(61)*.025
        p=20*np.c_[np.cos(angles),np.sin(angles)]
        expected=angles+np.pi/2
        self.assertTrue(np.allclose(headings(p,np.pi/2),expected,atol=.001))
    def test_settling_includes_start_of_half_second(self):
        g=fixture();p=np.c_[np.linspace(5,20,61),np.full(61,3.5)]
        p[-6,1]=1.0
        route={'matched':True,'lane_changes':[{'step':20,'to':'b'}]}
        g.settled_lane_changes(route,p,0,4,2)
        self.assertFalse(route['lane_changes'][0]['settled_for_last_half_second'])
    def test_straight_crosses_connector(self):
        p=np.c_[np.arange(5,66),np.zeros(61)]
        m=fixture().match(p,0)
        self.assertTrue(m['matched']);self.assertEqual(m['route'],['a','c','e'])
        self.assertEqual(m['lane_changes'],[])
    def test_lane_change_then_connector(self):
        x=np.arange(5,66); y=np.clip((x-10)/15,0,1)*3.5
        m=fixture().match(np.c_[x,y],0)
        self.assertTrue(m['matched']);self.assertEqual(m['lane_changes'][0]['action'],'lane_change_left')
        self.assertEqual(m['route'][-1],'f')
    def test_wrong_way(self):
        m=fixture().match(np.c_[np.linspace(20,10,61),np.zeros(61)],np.pi)
        self.assertFalse(m['matched'])
    def test_disconnected_geometry_not_enough(self):
        g=fixture();g.edges={};g.paths.cache_clear()
        self.assertFalse(g.match(np.c_[np.arange(5,66),np.zeros(61)],0)['matched'])
    def test_vehicle_width_matters(self):
        p=np.c_[np.linspace(5,20,61),np.full(61,-1.4)]
        self.assertTrue(fixture().match(p,0)['matched'])
        self.assertFalse(fixture().body_check(p,0,4,2)['passed'])
    def test_motion(self):
        p=np.c_[np.arange(61),np.zeros(61)]
        self.assertTrue(motion_check(p,[10,0])['passed'])
        p[20,1]=5
        self.assertFalse(motion_check(p,[10,0])['passed'])
    def test_collision_forecast(self):
        p=np.c_[np.arange(61),np.zeros(61)]
        obs=[{'id':'other','xy':[30,15],'velocity':[0,-5],'heading':-np.pi/2,'length':4,'width':2,'category':'vehicle'}]
        self.assertFalse(collision_check(p,0,4,2,obs)['passed'])
        self.assertTrue(collision_check(p,0,4,2,[])['passed'])

if __name__=='__main__':unittest.main()
