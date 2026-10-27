"""Geometric oracle: read raw map edges/baselines, not planner movements.

Check every point and transition, including actual vehicle samples. Explicit
fixture lane sequences additionally catch a geometrically smooth wrong branch.
"""
import math
import numpy as np
from shapely.geometry import Point, LineString, box
from shapely.prepared import prep
from shapely.ops import unary_union
from engine.geometry import arc, tangent, angle_diff, footprint


def audit_reverse(scene, state, route, actual=None, expected_nodes=None):
    assert route.get('reverse'), 'reverse gear missing'
    assert route.get('retrace_history') is False, 'ordinary reverse retraces history'
    sections=route.get('segments',[])
    assert sections, 'reverse has no lane identity'
    keys=[s['node_id'] for s in sections]
    if expected_nodes is not None:
        assert keys==expected_nodes, ('wrong backward lane correspondence',keys,expected_nodes)
    nodes=scene.nodes
    start=Point(state['xy'])
    assert nodes[keys[0]].baseline.distance(start)<.81, 'reverse did not start in the current lane'
    for a,b in zip(keys,keys[1:]):
        assert scene.edges.get(b,{}).get(a)=='forward', ('reverse crosses a lateral/nonadjacent edge',a,b)
    for key in keys:
        if nodes[key].kind!='connector':continue
        sources=[k for k,es in scene.edges.items() if es.get(key)=='forward' and nodes[k].kind=='lane']
        targets=[k for k,r in scene.edges.get(key,{}).items() if r=='forward' and nodes[k].kind=='lane']
        assert len(sources)==len(targets)==1, ('ambiguous connector',key)
        source,target=nodes[sources[0]],nodes[targets[0]]
        delta=abs(angle_diff(tangent(target.baseline,target.baseline.coords[0]),
                             tangent(source.baseline,source.baseline.coords[-1])))
        if delta>math.radians(30):
            # A bend has only one non-U-turn destination road group.
            # A turning path through an intersection is not a natural bend.
            forward_groups=set();back_groups=set()
            for lane in scene.graph.lane_groups[source.lane_group]:
                for c,r in scene.edges.get(lane.key,{}).items():
                    if r!='forward':continue
                    for t,rel in scene.edges.get(c,{}).items():
                        n=nodes[t]
                        if rel=='forward' and n.kind=='lane' and abs(angle_diff(tangent(n.baseline,n.baseline.coords[0]),tangent(lane.baseline,lane.baseline.coords[-1])))<math.radians(150):
                            forward_groups.add(n.lane_group)
            for lane,es in scene.edges.items():
                if nodes[lane].kind!='lane':continue
                for c,r in es.items():
                    if r!='forward':continue
                    if any(rel=='forward' and nodes[t].kind=='lane' and nodes[t].lane_group==target.lane_group for t,rel in scene.edges.get(c,{}).items()):
                        if abs(angle_diff(tangent(target.baseline,target.baseline.coords[0]),tangent(nodes[lane].baseline,nodes[lane].baseline.coords[-1])))<math.radians(150):
                            back_groups.add(nodes[lane].lane_group)
            assert delta<math.radians(120) and len(forward_groups)==1, ('unrequested junction turn',key)
    points=np.asarray(route['points'] if actual is None else [p['xy'] for p in actual])
    distances=arc(points) if actual is None else np.asarray([p['distance'] for p in actual])
    max_error=0.;previous={}
    for i,(xy,d) in enumerate(zip(points,distances)):
        matches=[s for s in sections if s['start']-.03<=d<=s['end']+.03]
        assert matches, ('unlabelled reverse geometry',float(d))
        owner=min(matches,key=lambda s:nodes[s['node_id']].baseline.distance(Point(xy)))
        line=nodes[owner['node_id']].baseline
        error=line.distance(Point(xy));max_error=max(max_error,error)
        assert error<=.81, ('extra lateral movement during reverse',error,xy.tolist())
        projection=line.project(Point(xy));last=previous.get(owner['node_id'],projection)
        assert projection<=last+.05, ('reverse moves forward on lane',owner['node_id'])
        previous[owner['node_id']]=projection
        if actual is not None:
            assert abs(angle_diff(actual[i]['heading'],tangent(line,xy)))<.36, 'reverse body heading is inconsistent with the lane'
    if actual is not None:
        bounds=LineString(points).bounds
        surface=scene.graph.surface.intersection(box(bounds[0]-4,bounds[1]-4,bounds[2]+4,bounds[3]+4))
        prepared=prep(surface);outside=[]
        for p in actual:
            body=footprint(p['xy'],p['heading'],4.8,2)
            outside.append(0 if prepared.covers(body) else body.difference(surface).area)
        assert outside[-1]<.02 and all(b<=a+.02 for a,b in zip(outside,outside[1:])), 'reverse footprint left the mapped road'
    return dict(nodes=keys,samples=len(points),max_lateral_error_m=max_error)
