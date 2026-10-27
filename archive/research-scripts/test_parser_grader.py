import unittest,copy
from benchmark_providers import CASES,check
def plan(action='go_straight',distance=60):
 return {'status':'parsed','unresolved_text':[],'stages':[{'action':action,'trigger':'now','travel_distance_m':distance,'target_speed_mps':None,'stop_at_end':True,'lane_reference':'none','lane_number':None}]}
class GraderTests(unittest.TestCase):
 def test_distance(self):
  self.assertEqual(check(plan(),CASES[0]),[])
  self.assertTrue(check(plan(distance=6),CASES[0]))
 def test_wrong_action(self):self.assertTrue(check(plan(action='turn_right'),CASES[0]))
 def test_negation(self):
  self.assertTrue(check(plan(action='turn_left'),CASES[5]))
  self.assertFalse(check({'status':'needs_clarification','stages':[],'unresolved_text':['Do not turn left.']},CASES[5]))
 def test_ambiguity_cannot_execute(self):self.assertTrue(check(plan(),CASES[6]))
 def test_ambiguity_unsupported_placeholder_is_valid(self):
  p=plan('unsupported',None);p['status']='needs_clarification'
  self.assertFalse(check(p,CASES[6]))
 def test_missing_units_partial_is_valid_but_invented_speed_is_not(self):
  p=plan('set_speed',None);p['status']='needs_clarification'
  self.assertFalse(check(p,CASES[12]));p['stages'][0]['target_speed_mps']=20
  self.assertTrue(check(p,CASES[12]))
 def test_speed_units(self):
  p=plan('set_speed',None);p['stages'][0].update(target_speed_mps=15,stop_at_end=False)
  self.assertTrue(check(p,CASES[3]));p['stages'][0]['target_speed_mps']=6.7056
  self.assertFalse(check(p,CASES[3]))
 def test_signal_not_immediate(self):
  p=plan('turn_right',None);p['stages'][0]['stop_at_end']=False
  self.assertTrue(check(p,CASES[7]));p['stages'][0]['trigger']='traffic_light';self.assertFalse(check(p,CASES[7]))
if __name__=='__main__':unittest.main()
