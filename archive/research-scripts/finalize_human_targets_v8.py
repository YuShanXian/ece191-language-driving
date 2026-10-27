import json
from mtr_project.paths import ROOT,write_json
out=ROOT/'runs/project-v3/human-target-v8';data=json.loads((out/'results.json').read_text())
for w in data['windows']:
 for ch in w['choices']:
  for key in ['effective_action','navigation','checks','mtr_grounded_candidates','map_supplement_count','repair_problem'] :ch.pop(key,None)
  ch['effective_goal']='follow_one_human_selected_feasible_road';ch['target_source']='human_annotations_used_as_input'
write_json(out/'results.json',data)
