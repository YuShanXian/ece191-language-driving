from pathlib import Path
p=Path('historical-project/scripts/select_review_instruction.py');s=p.read_text(encoding='utf-8-sig');needle=" if policy=='automatic_roads':"
block=''' if policy=='centerline_planner':
  base=ROOT/'runs/project-v3/centerline-planner-v1'
  ch=next(r for r in json.loads((base/'results.json').read_text())['rows'] if r['scene']==scene and r['command']==j)
  return {'scene':scene,'input':instruction,'action':action,'policy':policy,'status':'offline_plan_output','result':ch,'trajectory_file':str(base/f'scene-{scene:02d}-selected.npz'),'trajectory_key':f'command_{j}','scope':'Cached deterministic map-centerline plan for fixed development scene. No MTR candidates used. Risk checks are separate; no obstacle avoidance or live vehicle commands.'}
'''
if block not in s:s=s.replace(needle,block+needle)
s=s.replace("'human_targets','automatic_roads']","'human_targets','automatic_roads','centerline_planner']");p.write_text(s,encoding='utf-8')
source=Path('historical-project/scripts/serve_human_target_report.py').read_text();source=source.replace('human-target-v8','centerline-planner-v1').replace('8772','8774');Path('historical-project/scripts/serve_centerline_report.py').write_text(source)
