from pathlib import Path
import shutil
root=Path('historical-project');out=root/'runs/project-v3/automatic-road-v9'
for name in ['predictions.json','road-evaluation.json']:shutil.copy2(out/name,out/('baseline-'+name))
p=root/'scripts/automatic_road_selector.py';shutil.copy2(p,out/'baseline-selector.py');s=p.read_text(encoding='utf-8-sig')
s=s.replace("'end_left_m':float(rel@l)","'end_left_m':float(rel@l),'entry_distance_m':float(length-line.length)")
s=s.replace("abs(b['exit_angle_deg']),b['length_m']","abs(b['end_left_m'])+.1*abs(b['exit_angle_deg']),b['length_m']")
s=s.replace("(b['length_m'],abs(b['exit_angle_deg']))","(abs(b['exit_angle_deg']),b['length_m'])")
s=s.replace("40<=sign*b['exit_angle_deg']<=145","40<=sign*b['exit_angle_deg']<=120 and b['end_forward_m']>0 and b['entry_distance_m']<=60 and sign*b['end_left_m']>0")
s=s.replace("(b['length_m']+3*abs(b['lateral_m']-current['lateral_m']),abs(abs(b['exit_angle_deg'])-90))","(abs(b['lateral_m']-current['lateral_m']),abs(b['exit_angle_deg']),b['length_m'])")
a=s.index("  neighbors=[a for a in approaches")
b=s.index(" elif action not in",a)
s=s[:a]+'''  # Compare onward lanes, not approach lanes that may be turn-only.
  base=selected
  onward=[b for b in branches if b['approach']==base['approach'] and b['path'][:len(base['path'])]==base['path'] and abs(b['exit_angle_deg']-base['exit_angle_deg'])<20]
  if onward:
   far=max(b['end_forward_m'] for b in onward)
   farther=[b for b in onward if b['end_forward_m']>=far-8]
   base=min(farther,key=lambda b:abs(b['end_left_m']-selected['end_left_m']))
  theta=np.radians(base['exit_angle_deg']);normal=np.array([-np.sin(theta),np.cos(theta)])
  options=[]
  for b in branches:
   delta=np.array([b['end_forward_m']-base['end_forward_m'],b['end_left_m']-base['end_left_m']]);side=float(delta@normal)
   longitudinal=float(contact-removed([np.cos(theta),np.sin(theta)]))
   if 2<sign*side<7 and abs(longitudinal)<12 and abs(b['exit_angle_deg']-base['exit_angle_deg'])<20:
    options.append((abs(side),abs(b['lateral_m']-current['lateral_m']),b['length_m'],b))
  if options:selected=min(options,key=lambda t:t[:3])[3];reason='adjacent_onward_lane'
  else:selected=base;reason='no_adjacent_onward_lane_continue_road'
''' +s[b:]
# Include the uniquely connected exit lane, so graph-ID evaluation can recognize selected exit lanes.
s=s.replace(" return {'status':'selected'", " next_lanes=[k for k,r in graph.edges.get(selected['target'],{}).items() if r=='forward']\n selected=dict(selected)\n if len(next_lanes)==1:selected['path']=selected['path']+next_lanes\n return {'status':'selected'")
p.write_text(s,encoding='utf-8')
