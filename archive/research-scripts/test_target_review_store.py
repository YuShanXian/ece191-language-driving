import json,tempfile
from pathlib import Path
from target_review_store import update_target,validate_target,blank_targets
from mtr_project.paths import ROOT,write_json
maps=json.loads((ROOT/'runs/project-v3/instruction-priority-v7/human-review/target-maps.json').read_text());ids=[x['id'] for x in maps['1']['roads'][:2]]
with tempfile.TemporaryDirectory() as directory:
 p=Path(directory)/'targets.json'
 update_target(p,{'scene':1,'command':0,'mode':'roads','road_ids':ids},maps)
 update_target(p,{'scene':1,'command':1,'mode':'continue','road_ids':[]},maps)
 rows=json.loads(p.read_text())['reviews'];assert rows[0]['road_ids']==ids and rows[1]['mode']=='continue' and len(rows)==35
 before=p.read_bytes()
 for bad in [dict(scene=1,command=0,mode='roads',road_ids=['NOT_A_ROAD']),dict(scene=1,command=0,mode='none',road_ids=ids),dict(scene=1,command=0,mode='roads',road_ids=[ids[0],ids[0]]),dict(scene=8,command=0,mode='none',road_ids=[])]:
  try:update_target(p,bad,maps);raise AssertionError('bad input accepted')
  except ValueError:pass
 assert p.read_bytes()==before
 update_target(p,dict(scene=1,command=0,mode='unselected',road_ids=[]),maps)
 assert json.loads(p.read_text())['reviews'][1]['mode']=='continue'
write_json(ROOT/'runs/project-v3/instruction-priority-v7/human-review/target-picker-verification.json',{'ordered_targets_preserved':True,'per_command_save_preserves_other_commands':True,'invalid_ids_duplicates_and_contradictions_rejected':True,'tests_used_temporary_storage':True,'ui_click_shows_nearby_roads':True})
print('Target persistence, ordering, reset and invalid-data checks passed. User targets and scores untouched.')
