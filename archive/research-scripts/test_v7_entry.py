from select_review_instruction import resolve
assert resolve(4,'Turn left')['status']=='requested_action_refused'
assert resolve(5,'Turn right')['result']['horizon_s']==12
assert resolve(7,'Change lanes to the right')['result']['effective_action']=='continue_without_requested_lane_change'
assert resolve(3,'Turn right')['status']=='no_road_target'
assert resolve(2,'Change lanes to the right')['status']=='road_target_output'
print('5 updated command entry checks passed')
