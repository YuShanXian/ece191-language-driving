"""Exercise actual map geometry and stage transitions, without animation time shortcuts."""
import sys,json,math,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[2]))
from engine.scene import get_scene
from engine.planner import plan,stage
from engine.geometry import arc,validate_path,angle_diff,heading
from engine.routes import follow
from engine.normalize import normalize
from engine.contract import validate_stage
from engine.continuity import connection_geometry,straight_rank_error

results=[];failures=[]
def pose_at(route,distance):
    p=np.array(route['points']);s=arc(p);distance=min(distance,s[-1]-.01)
    xy=[float(np.interp(distance,s,p[:,j])) for j in range(2)]
    i=min(len(p)-2,max(0,int(np.searchsorted(s,distance))-1));delta=p[i+1]-p[i]
    node=next((x['node_id'] for x in route['segments'] if x['start']<=distance<x['end']),None)
    return {'xy':xy,'heading':math.atan2(delta[1],delta[0]),'speed':20/3.6,'target_speed_mps':20/3.6,'node_id':node,'history':p[max(0,i-150):i+1].tolist()}

for number in range(1,8):
    scene=get_scene(number);initial={'xy':[0,0],'heading':0,'speed':0,'target_speed_mps':20/3.6}
    for key,choices in scene.forward.items():
        if scene.nodes[key].kind!='lane' or not choices:continue
        next_key=choices[0]
        exits=[k for k,r in scene.edges.get(next_key,{}).items() if r=='forward' and scene.nodes[k].kind=='lane'] if scene.nodes[next_key].kind=='connector' else [next_key]
        if exits:
            turn,lateral=connection_geometry(scene.nodes[key],scene.nodes[exits[0]])
            assert not(abs(turn)<math.radians(30) and abs(lateral)>2.2 and straight_rank_error(scene.nodes[key],scene.nodes[exits[0]],scene.graph.lane_groups,scene.nodes,scene.edges)>0), 'Automatic crossing to an unrelated exit lane'
    states=[initial]
    # Cover positions before and after turns, intersections, lane ends and long straight sections.
    for action in ('turn_left','turn_right','go_straight'):
        result=plan({'scene':number,'state':initial,'stage':stage(action)})
        if result.get('route'):
            route=result['route']
            for distance in (20,60,120,300,700,1200,1800,route['length']-1):
                if 1<distance<route['length']:states.append(pose_at(route,distance))
    for index,state in enumerate(states):
        for action in ('turn_left','turn_right','go_straight','lane_change_left','lane_change_right','u_turn','reverse','pull_over','continuous_drive'):
            started=time.perf_counter()
            try:
                result=plan({'scene':number,'state':state,'stage':stage(action),'remaining':20})
                route=result.get('route')
                if route:
                    p=np.array(route['points']);assert np.linalg.norm(p[0]-state['xy'])<.15, 'route starts off pose'
                    valid,reason=validate_path(p);assert valid,reason
                    initial_heading=math.atan2(*(p[1]-p[0])[::-1])+(math.pi if route.get('reverse') else 0)
                    assert abs(angle_diff(initial_heading,state['heading']))<.35,'incompatible initial heading'
                    if result['status']=='ready':assert 0<=result['completion_m']<=arc(p)[-1]+.1
                    if action=='continuous_drive':
                        for section in route['segments']:
                            k=section['node_id']
                            if scene.nodes[k].kind=='connector':assert abs(angle_diff(heading(scene.points[k],True),heading(scene.points[k])))<math.radians(150),'automatic U-turn'
                results.append({'scene':number,'position':index,'action':action,'status':result['status'],'ms':round((time.perf_counter()-started)*1000,2)})
            except Exception as error:
                failures.append({'scene':number,'position':index,'state':state,'action':action,'error':str(error)})
    print('scene',number,'cases',len(results),'failures',len(failures),flush=True)

# Parser normalization must retain explicit maneuver order and reject unsupported extra fields.
plan_data={'stages':[dict(stage('lane_change_left'),lane_number=3),stage('turn_left')]}
normalized=normalize(plan_data)
assert [s['action'] for s in normalized['stages']]==['lane_change_left']*3+['turn_left']
for st in normalized['stages']:validate_stage(st)
report={'cases':len(results),'failures':failures,'results':results}
out=Path(__file__).parents[1]/'results/engine-regression.json';out.write_text(json.dumps(report,indent=2))
print(json.dumps({'cases':len(results),'failures':len(failures),'p95_ms':float(np.percentile([r['ms'] for r in results],95)),'report':str(out)}),flush=True)
sys.exit(bool(failures))
