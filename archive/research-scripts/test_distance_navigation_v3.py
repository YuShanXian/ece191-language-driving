import json
from pathlib import Path
from execute_language_plan_v3 import execute
from mtr_project.paths import ROOT
p=next((ROOT/'runs/project-v3/llm-parser-v3').glob('*/parsed.json'));base=json.loads(p.read_text());stage=base['stages'][-1].copy();stage.update(trigger='now',travel_distance_m=30,source_clause='Drive 30 meters and stop.')
results=[]
for scene in range(1,8):
 r=execute(scene,{'status':'parsed','unresolved_text':[],'stages':[stage]});results.append(r);print(scene,r['status'],[(s.get('traveled_distance_m'),s.get('final_speed_mps')) for s in r['stages']],flush=True)
 if r['status']=='completed_offline':assert abs(r['stages'][0]['traveled_distance_m']-30)<.25 and r['speed_mps'][-1]<.05
out=ROOT/'runs/project-v3/map-navigation-v3';out.mkdir(exist_ok=True);(out/'distance-tests.json').write_text(json.dumps(results,indent=2))
