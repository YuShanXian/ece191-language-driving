import json,copy,math
from fixtures import ROOT,load_scene
import engine.planner as planner
from engine.geometry import tangent
from reverse_audit import audit_reverse
planner.get_scene=load_scene
s=load_scene(1);reports=[]
for number,keys in [(5,['L67838','C69442','L67723','C69385','L63474']),
                    (12,['C69865','L67763','C68798','L63443','C69459','L67829','C69749'])]:
    old=json.loads((Path(__file__).resolve().parents[1]/'results/historical-v36/human-review-reverse'/f'instruction-{number}-request.json').read_text())
    request=old['request'];result=planner.plan(request)
    assert result['status']=='ready',result
    route=result['route'];check=audit_reverse(s,request['state'],route,expected_nodes=keys)
    for history in ([],[[9,8],[7,6]],list(reversed(request['state']['history']))):
        altered=copy.deepcopy(request);altered['state']['history']=history
        assert planner.plan(altered)['route']==route,'history affected ordinary reverse'
    # Old acceptance routes must fail the new physical audit, even if their
    # metadata is rewritten to claim they are the new correct lane route.
    bad=copy.deepcopy(route);bad['points']=old['result']['route']['points']
    try:audit_reverse(s,request['state'],bad)
    except AssertionError as e: rejected=str(e)
    else:raise AssertionError('Old reverse regression was incorrectly accepted')
    reports.append(dict(case=number,**check,history_invariant=True,old_route_rejected=rejected,planning_ms=result['planning_ms']))
    fixture=dict(scene=1,state=request['state'],stage=request['stage'])
    (ROOT/'results'/f'reverse-{number}-fixture.json').write_text(json.dumps(fixture))
key='C64857';line=s.nodes[key].baseline;xy=list(line.interpolate(line.length*.85).coords[0])[:2]
state=dict(xy=xy,heading=tangent(line,xy),node_id=key,speed=0,history=[xy])
stage=planner.stage('reverse');stage['travel_distance_m']=min(25,line.length*.7)
req=dict(scene=1,state=state,stage=stage);result=planner.plan(req)
assert result['status']=='ready',result
check=audit_reverse(s,state,result['route']);assert abs(tangent(line,result['route']['points'][-1])-state['heading'])>.2
(ROOT/'results/reverse-bend-fixture.json').write_text(json.dumps(req))
reports.append(dict(case='natural-bend',**check))
(ROOT/'results/reverse-geometry-audit.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports,indent=2))
