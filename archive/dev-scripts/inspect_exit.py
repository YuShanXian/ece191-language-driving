import sys,pickle,json
from pathlib import Path
root=Path(__file__).parents[1];sys.path.insert(0,str(root.parents[1]/'sim'))
with (root/'results/scene1.pkl').open('rb') as f:s=pickle.load(f)
r=json.loads((root/'results/turn_right-fixed.json').read_text())
print('route',r['route']['length'],r['completion_m'],r['route'].get('boundary_reason'),r['route']['segments'])
for key in ['L67605','C70254']:
 n=s.nodes[key]
 print(key,n, 'edges',s.edges.get(key), 'continuation',s.continuation(key,0))
 for m in s.topology.by_lane.get(key,[]):
  print('MOVE',m,'target',s.nodes[m.target].baseline.length)
