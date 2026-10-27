from pathlib import Path
p=Path('historical-project/scripts/automatic_road_selector.py');s=p.read_text()
s=s.replace(" def straight(options):", " def continuity(b):\n  exits=[graph.nodes[k].lane_index for k,r in graph.edges.get(b['target'],{}).items() if r=='forward' and graph.nodes[k].lane_index is not None]\n  index=graph.nodes[b['approach']].lane_index\n  return min([abs(x-index) for x in exits],default=99)\n def straight(options):")
s=s.replace("  gentle=[b for b in options", "  nearest=min(b['entry_distance_m'] for b in options)\n  options=[b for b in options if b['entry_distance_m']<=nearest+12]\n  gentle=[b for b in options")
s=s.replace("(abs(b['exit_angle_deg']),b['length_m'])", "(continuity(b),abs(b['exit_angle_deg']),b['length_m'])")
s=s.replace("(abs(b['lateral_m']-current['lateral_m']),abs(b['exit_angle_deg']),b['length_m'])", "(abs(b['lateral_m']-current['lateral_m']),continuity(b),b['length_m'])")
s=s.replace("  if onward:\n", "  if onward and abs(base['exit_angle_deg'])<=30 and base['end_forward_m']<25:\n")
s=s.replace("  if options:selected=min(options,key=lambda t:t[:3])[3];reason='adjacent_onward_lane'", "  if abs(base['exit_angle_deg'])>30:\n   same=[o for o in options if o[3]['approach']==current['key']]\n   if same:options=same\n   else:\n    neighbors=[a for a in approaches if sign*(a['lateral_m']-current['lateral_m'])>2]\n    if neighbors:\n     nearest=min(neighbors,key=lambda a:abs(a['lateral_m']-current['lateral_m']))\n     nearbranches=[b for b in branches if b['approach']==nearest['key']]\n     if nearbranches:\n      b,_=straight(nearbranches);options=[(0,0,0,b)]\n  if options:selected=min(options,key=lambda t:t[:3])[3];reason='adjacent_onward_lane'")
p.write_text(s)
