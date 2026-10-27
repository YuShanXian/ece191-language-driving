import unittest
from language_selector import parse_instruction,StageTracker,select

def row(i,score,action=None,passed=True,settled=True):
    return {'candidate':i,'score':score,'passes_current_checks':passed,
            'route':{'matched':True,'turns':[],'lane_changes':([] if not action else [{'action':action,'settled_for_last_half_second':settled}])},
            'motion':{'end_speed_mps':10}}
class LanguageTests(unittest.TestCase):
    def test_original_label(self):
        self.assertEqual(parse_instruction('Merge to the right lane.')['stages'][0]['action'],'lane_change_right')
    def test_no_silent_loss_of_negation_or_grounding(self):
        for s in ['Do not turn right','Stop after the red car','Turn right at the next intersection','Merge right unless the lane is occupied']:
            self.assertEqual(parse_instruction(s)['status'],'unsupported')
    def test_no_candidates_does_not_force_selection(self):
        self.assertEqual(select('Merge to the right lane.',[row(1,.9)],10)['status'],'no_matching_candidate')
    def test_scene_fixed_instruction_changes_choice(self):
        rows=[row(1,.9),row(2,.05,'lane_change_left'),row(3,.03,'lane_change_right')]
        self.assertEqual(select('Merge to the left lane.',rows,10)['selected_candidate'],2)
        self.assertEqual(select('Merge to the right lane.',rows,10)['selected_candidate'],3)
    def test_rejects_failed_and_unfinished_changes(self):
        rows=[row(1,.9,'lane_change_right',False),row(2,.1,'lane_change_right',True,False)]
        self.assertIsNone(select('Merge to the right lane.',rows,10)['selected_candidate'])
    def test_stages_require_observed_completion(self):
        parsed=parse_instruction('Merge to the right lane then keep the lane.')
        state=StageTracker(parsed['stages']);self.assertEqual(state.active(),'lane_change_right')
        state.observe([]);self.assertEqual(state.active(),'lane_change_right')
        state.observe(['lane_change_right']);self.assertEqual(state.active(),'keep_lane')
    def test_unbounded_first_stage_rejected(self):
        self.assertEqual(parse_instruction('Go straight then turn right')['status'],'unsupported')
    def test_hold_stopped_cannot_drive_then_stop(self):
        r=row(1,.9);r['motion'].update(end_speed_mps=0,end_max_speed_mps=0,peaks={'speed_mps':2},max_displacement_m=3)
        self.assertEqual(select('Stop.',[r],0)['selected_candidate'],1)
        self.assertIsNone(select('Remain stopped.',[r],0)['selected_candidate'])
        r['motion'].update(peaks={'speed_mps':.1},max_displacement_m=.2)
        self.assertEqual(select('Remain stopped.',[r],0)['selected_candidate'],1)
    def test_stop_requires_whole_final_second(self):
        r=row(1,.9);r['motion'].update(end_speed_mps=.2,end_max_speed_mps=1.)
        self.assertIsNone(select('Stop.',[r],3)['selected_candidate'])
if __name__=='__main__':unittest.main()
