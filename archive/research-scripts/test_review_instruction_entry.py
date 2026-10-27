from select_review_instruction import resolve
assert resolve(1,'\u53f3\u8f6c')['status']=='road_target_output'
assert resolve(1,'Turn right')['result']['candidate']==resolve(1,'\u53f3\u8f6c')['result']['candidate']
assert resolve(3,'Change lanes to the right')['status']=='direction_only_no_road_target'
assert resolve(3,'Change lanes to the right',allow_direction_probe=False)['status']=='no_road_target'
assert resolve(1,'Turn left then turn right')['status']=='unsupported_trigger_or_sequence_for_cached_demo'
assert resolve(1,'Turn left after 5 seconds')['status']=='unsupported_trigger_or_sequence_for_cached_demo'
assert resolve(1,'Drive to the hospital')['status']=='unsupported_instruction'
assert resolve(8,'Go straight')['status']=='unsupported_scene'
assert resolve(1,'Turn left',policy='original_checked')['result']['choice']['candidate'] is None
print('9 command integration checks passed')
