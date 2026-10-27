exec(open(__file__.replace('inspect_right_lines.py','diagnose_right.py')).read().split('for state in')[0])
from engine.geometry import heading,tangent,angle_diff
from shapely.geometry import Point
for key in ['L63477','L63474','L63476','C70485','C68730','C69616','J_L63477_L67611','L63435','L63436']:
 n=s.nodes.get(key)
 if not n:continue
 p=np.asarray(n.baseline.coords)
 print(key,'kind',n.kind,'group',n.lane_group,'rank',n.lane_index,'ends',p[[0,-1]].tolist(),'headings',math.degrees(heading(p)),math.degrees(heading(p,True)), 'edges',s.edges.get(key),flush=True)
 print('movement',s.topology.by_connector.get(key),flush=True)
 if key.startswith('C'):print('incoming',[(k,r[key]) for k,r in s.edges.items() if key in r],flush=True)
