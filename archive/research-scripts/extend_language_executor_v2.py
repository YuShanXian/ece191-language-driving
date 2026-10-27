from mtr_project.paths import ROOT
p=ROOT/'scripts/execute_language_plan_v2.py';s=p.read_text(encoding='utf-8-sig')
s=s.replace("if st['lane_number'] not in (None,1) and action!='select_lane':return block('Multiple relative lane changes need explicit per-lane completion.')", "if st['lane_number'] not in (None,1) and action!='select_lane':return block('Multiple relative lane changes need explicit per-lane completion.')")
a=s.index("   n=graph.nodes[road['current']['key']]");b=s.index("  if action in ('go_straight'",a)
s=s[:a]+'''   n=graph.nodes[road['current']['key']];normal=np.array([-np.sin(center[6]),np.cos(center[6])]);pos=Point(center[:2])
   group=[x for x in graph.nodes.values() if x.kind=='lane' and x.lane_group==n.lane_group and abs(angle_diff(tangent(x.baseline,center[:2]),center[6]))<np.radians(30)]
   group.sort(key=lambda x:float((np.asarray(x.baseline.interpolate(x.baseline.project(pos)).coords[0])[:2]-center[:2])@normal),reverse=st['lane_reference']=='leftmost')
   number=st['lane_number']
   if st['lane_reference'] not in ('leftmost','rightmost') or type(number) is not int or not 1<=number<=len(group):return block('Requested ordinal lane does not exist in the current same-direction lane group.')
   target=group[number-1].key;keys=[target];road['reason']='ordinal_lane_by_physical_left_right'
''' +s[b:]
s=s.replace("elif action in ('turn_left','turn_right','lane_change_left','lane_change_right'):","elif action in ('turn_left','turn_right','lane_change_left','lane_change_right','select_lane'):")
p.write_text(s)
