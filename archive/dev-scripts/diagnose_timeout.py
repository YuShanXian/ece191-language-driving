import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.routes import turn,assemble
from engine.geometry import heading,angle_diff
root=Path('historical-project/runs/project-v3/refactor-v27')
out=Path(__file__).parents[1]/'results'
cases=[]
for p in sorted((root/'requests').glob('*.json')):
 d=json.loads(p.read_text()); r=d.get('request',{}); t=d.get('time','')
 if (r.get('stage',{}).get('action')=='turn_left' and '2026-10-24T06:26:' in t) or (r.get('stage',{}).get('action')=='turn_right' and '2026-10-24T06:39:' in t):cases.append(d)
cases.sort(key=lambda x:x['time'])
selected=[]
for action in ('turn_left','turn_right'):
 subset=[x for x in cases if x['request']['stage']['action']==action]
 print('CASE',action,'requests',len(subset),flush=True)
 if not subset:continue
 for d in (subset[0],subset[-1]):
  r=d['request'];s=get_scene(r['scene']);state=r['state'];key,start=s.locate(state)
  print(d['id'],d['time'],{k:v for k,v in state.items() if k!='history'},'remaining',r.get('remaining'),flush=True)
  found=turn(s,state,action);print('chosen', None if not found else {'begin':found[1],'completion':found[2],'connector':found[3]},flush=True)
  distance=0;lead=[]
  for k,a,b in s.continuation(key,start,500):
   node=s.nodes[k];lead.append((k,a,b))
   if node.kind=='lane':
    print('lane',k,'at',round(distance,1),'index',node.lane_index,flush=True)
    for c,rel in s.edges.get(k,{}).items():
     if rel!='forward' or s.nodes[c].kind!='connector':continue
     deg=math.degrees(angle_diff(heading(s.points[c],True),heading(s.points[c])))
     dest=list(s.edges.get(c,{}));errors=[]
     for target in dest:
      try:assemble(s,lead+[(c,0,s.nodes[c].baseline.length)]+s.continuation(target),state);errors.append('valid')
      except ValueError as e:errors.append(str(e))
     print('  exit',c,'deg',round(deg,1),'targets',dest,'geometry',errors,flush=True)
   distance+=b-a
  selected.append(d)
(out/'timeout-fixtures.json').write_text(json.dumps(selected))
