from pathlib import Path
p=Path('historical-project/scripts/select_review_instruction.py');s=p.read_text(encoding='utf-8-sig');needle=" if policy=='original_checked':"
addition=''' if policy=='automatic_roads':
  base=ROOT/'runs/project-v3/automatic-road-v9'
  road=next(r for r in json.loads((base/'predictions.json').read_text())['rows'] if r['scene']==scene and r['command']==j)
  ch=next(r for r in json.loads((base/'trajectory-results.json').read_text())['rows'] if r['scene']==scene and r['command']==j)
  result={'scene':scene,'input':instruction,'action':action,'policy':policy,'road_decision':road,'result':ch,'status':ch['status'],'scope':'Cached automatic map/state/text selection for seven development scenes. Human labels used only in separate evaluation. Rule parser, no LLM, no vehicle commands.'}
  if ch['status']=='route_output':result.update(trajectory_file=str(base/f'scene-{scene:02d}-selected.npz'),trajectory_key=f'command_{j}')
  return result
'''
s=s.replace(needle,addition+needle).replace("choices=['instruction_priority','original_checked','human_targets']","choices=['instruction_priority','original_checked','human_targets','automatic_roads']");p.write_text(s,encoding='utf-8')
