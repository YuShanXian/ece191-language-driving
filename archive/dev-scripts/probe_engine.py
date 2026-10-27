import sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'sim'))
from engine.scene import get_scene
from engine.planner import plan,stage
from engine.geometry import arc
import numpy as np
reports=[]
for number in (1,7):
    started=time.perf_counter();scene=get_scene(number)
    print('loaded',number,len(scene.nodes),round(time.perf_counter()-started,2),flush=True)
    state={'xy':[0,0],'heading':0,'speed':0,'target_speed_mps':20/3.6}
    for action in ('turn_left','turn_right','go_straight','lane_change_left','lane_change_right'):
        started=time.perf_counter();r=plan({'scene':number,'state':state,'stage':stage(action)})
        summary={k:v for k,v in r.items() if k!='route'}
        summary.update(scene=number,route_points=len(r.get('route',{}).get('points',[])),elapsed_ms=round((time.perf_counter()-started)*1000,1))
        reports.append(summary);print(json.dumps(summary),flush=True)
(Path(__file__).parents[1]/'results/engine-probe.json').write_text(json.dumps(reports,indent=2))
