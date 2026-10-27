import json,time
from fixtures import ROOT, load_scene
import engine.planner as planner
planner.get_scene=load_scene
results=[]
for number in (5,12):
    data=json.loads((ROOT.parent/'refactor-v36/results/human-review-reverse'/f'instruction-{number}-request.json').read_text())
    start=time.perf_counter();r=planner.plan(data['request'])
    print(number,round(time.perf_counter()-start,2),r['status'],r.get('reason'),flush=True)
    print(r.get('route',{}).get('segments') if r.get('route') else '')
    results.append(dict(number=number,request=data['request'],response=r))
(ROOT/'results/reverse-probes.json').write_text(json.dumps(results))
