from pathlib import Path
p=Path('historical-project/scripts/select_review_instruction.py');s=p.read_text()
s=s.replace("if policy!='instruction_priority':", "if policy not in ('instruction_priority','human_targets'):")
s=s.replace("base=ROOT/'runs/project-v3/instruction-priority-v7'", "base=ROOT/('runs/project-v3/human-target-v8' if policy=='human_targets' else 'runs/project-v3/instruction-priority-v7')")
old="context=next(r for r in json.loads((base/'context-risk.json').read_text())['results'] if r['scene']==scene and r['command']==j)"
new="context=({'status':'not_recomputed_for_human_target_policy','trajectory_risk_flags':ch.get('risk_flags',[])} if policy=='human_targets' else next(r for r in json.loads((base/'context-risk.json').read_text())['results'] if r['scene']==scene and r['command']==j))"
assert old in s;s=s.replace(old,new)
s=s.replace("choices=['instruction_priority','original_checked']", "choices=['instruction_priority','original_checked','human_targets']")
s=s.replace("if ch['status']=='destination_grounded_offline':", "if policy=='human_targets':result['scope']='Cached human-target-conditioned experiment: annotated feasible roads were used as inputs; not independent language accuracy.'\n if ch['status']=='destination_grounded_offline':")
p.write_text(s,encoding='utf-8')
