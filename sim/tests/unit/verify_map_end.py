import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]))
from engine.scene import get_scene
s=get_scene(1);key='L67444'
forward={k:r for k,r in s.edges.get(key,{}).items() if r=='forward'}
assert not forward,forward
assert not s.forward[key]
result={'scene':1,'terminal_lane':key,'raw_forward_edges':forward,'end':list(s.nodes[key].baseline.coords[-1])[:2],'verified':True}
(Path(__file__).parents[1]/'results/map-end.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
