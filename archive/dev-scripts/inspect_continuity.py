import sys,math,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.continuity import connection_geometry
bad=[]
for number in range(1,8):
 scene=get_scene(number)
 for key,choices in scene.forward.items():
  if scene.nodes[key].kind!='lane' or not choices:continue
  nxt=choices[0]
  exits=[n for n,r in scene.edges.get(nxt,{}).items() if r=='forward' and scene.nodes[n].kind=='lane'] if scene.nodes[nxt].kind=='connector' else [nxt]
  if not exits:continue
  turn,lateral=connection_geometry(scene.nodes[key],scene.nodes[exits[0]])
  if abs(turn)<math.radians(30) and abs(lateral)>2.2:bad.append({'scene':number,'source':key,'next':nxt,'target':exits[0],'turn_deg':math.degrees(turn),'lateral':lateral})
 print('scene',number,'suspicious',len(bad),flush=True)
(Path(__file__).parents[1]/'results/continuity-inspection.json').write_text(json.dumps(bad,indent=2))
print(json.dumps(bad[:12]),flush=True)
