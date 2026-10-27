import json,numpy as np
from mtr_project.paths import ROOT
from execute_language_plan_v4 import execute
folders=[p.parent for p in (ROOT/'runs/project-v3/llm-parser-v4').glob('*/start-state.json')];folder=max(folders,key=lambda p:p.name);state=json.loads((folder/'start-state.json').read_text(encoding='utf-8-sig'));plan=json.loads((folder/'parsed.json').read_text());r=execute(7,plan,state);assert np.linalg.norm(np.array(r['points'][0])-state['xy'])<.001;print(json.dumps({'state':state,'status':r['status'],'stages':r['stages']},indent=2));(ROOT/'runs/project-v3/live-replanning-v6/moving-stop-test.json').write_text(json.dumps({'state':state,'result':r},indent=2))
