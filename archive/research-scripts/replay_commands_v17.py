import json,sys
from pathlib import Path
import numpy as np
from functools import lru_cache
r=Path('historical-project');sys.path.insert(0,str(r/'scripts'))
import free_navigation_v8
free_navigation_v8.context=lru_cache(8)(free_navigation_v8.context)
from execute_language_plan_v4 import execute
raw=r/'runs/project-v3/provider-benchmark-20261020/raw';out=r/'runs/project-v3/command-audit-v17';out.mkdir(exist_ok=True)
rows=[]
dirs=sorted(raw.iterdir(),key=lambda d:d.stat().st_mtime,reverse=True)
for d in dirs:
 if not (d/'request.json').exists() or not (d/'execution.json').exists() or not (d/'start-state.json').exists():continue
 old=json.loads((d/'execution.json').read_text());q=json.loads((d/'request.json').read_text());state=json.loads((d/'start-state.json').read_text());plan=json.loads((d/'parsed.json').read_text())
 if len(rows)>=18:break
 if old.get('status') in ('completed_offline','live_control'):continue
 scene=old.get('scene',7)
 try:
  e=execute(scene,plan,state,'free');(out/(d.name+'.json')).write_text(json.dumps(e));status=e['status'];reason=e.get('reason') or ' / '.join(x.get('reason','') for x in e.get('stages',[]));changes=[c for s in e.get('stages',[]) for c in s.get('preparatory_lane_changes',[])]
  if e.get('status')=='completed_offline':assert np.linalg.norm(np.asarray(e['points'][0])-state['xy'])<1e-4
 except Exception as ex:status='error';reason=repr(ex);changes=[]
 row={'id':d.name,'input':q['instruction'],'scene':scene,'before':old['status'],'after':status,'reason':reason,'lane_changes':changes};rows.append(row);print(json.dumps(row),flush=True);(out/'replay.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
