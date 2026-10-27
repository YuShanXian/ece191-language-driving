from pathlib import Path
root=Path('historical-project/scripts')
p=root/'annotate_navigation_context.py';s=p.read_text().replace('instruction-priority-v6','instruction-priority-v7')
old="  p=paths[f'command_{j}'] if f'command_{j}' in paths else np.load(ROOT/f'runs/project-v3/forced-direction-probes-v1/scene-{w[\"scene\"]:02d}-command-{j}.npz')['points']"
new="  if f'command_{j}' not in paths:\n   results.append({'scene':w['scene'],'command':j,'status':'no_road_route','note':'No trajectory to annotate.'});continue\n  p=paths[f'command_{j}']"
assert old in s;s=s.replace(old,new);(root/'annotate_v7_context.py').write_text(s)
p=root/'select_review_instruction.py';s=p.read_text().replace('instruction-priority-v6','instruction-priority-v7').replace('allow_direction_probe=True','allow_direction_probe=False')
s=s.replace("elif action=='go_straight':", "elif ch['status']=='refused_no_reachable_road':\n  result['status']='requested_action_refused'\n elif action=='go_straight':")
s=s.replace("p.add_argument('--no-direction-probe',action='store_true')", "p.add_argument('--no-direction-probe',action='store_true')\n p.add_argument('--direction-probe',action='store_true',help='Explicit diagnostic geometry only, not an executable road route')")
s=s.replace("not args.no_direction_probe)","args.direction_probe and not args.no_direction_probe)");p.write_text(s)
