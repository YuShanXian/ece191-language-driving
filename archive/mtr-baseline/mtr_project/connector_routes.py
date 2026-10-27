"""Explicit geometric hypothesis: lateral motion between parallel connectors.

Two connectors must enter and exit adjacent lanes in the same direction, have
similar endpoint headings, and touch within the existing map tolerance.
This does NOT establish lane-marking legality or permission to change lanes.
"""
import math
from trajectory_checks import RoadGraph,angle_diff,tangent


def add_parallel_connector_edges(graph,maximum_heading_degrees=15.):
    edges={key:dict(value) for key,value in graph.edges.items()};incoming={}
    for source,links in graph.edges.items():
        for target,direction in links.items():
            if direction=='forward':incoming.setdefault(target,[]).append(source)
    added=[]
    for key,node in graph.nodes.items():
        if node.kind!='connector':continue
        before=incoming.get(key,[])
        after=[k for k,v in graph.edges.get(key,{}).items() if v=='forward']
        if len(before)!=1 or len(after)!=1:continue
        if any(graph.nodes[k].kind!='lane' for k in before+after):continue
        for neighbor,direction in graph.edges.get(before[0],{}).items():
            if direction not in ('left','right'):continue
            for candidate,link in graph.edges.get(neighbor,{}).items():
                other=graph.nodes[candidate]
                if link!='forward' or other.kind!='connector':continue
                other_before=incoming.get(candidate,[])
                other_after=[k for k,v in graph.edges.get(candidate,{}).items() if v=='forward']
                if other_before!=[neighbor] or len(other_after)!=1:continue
                if graph.edges.get(after[0],{}).get(other_after[0])!=direction:continue
                if node.polygon.distance(other.polygon)>2*graph.tolerance:continue
                differences=[abs(angle_diff(tangent(node.baseline,node.baseline.interpolate(f,normalized=True)),
                                            tangent(other.baseline,other.baseline.interpolate(f,normalized=True)))) for f in (0.,1.)]
                if max(differences)>math.radians(maximum_heading_degrees):continue
                if candidate in edges.get(key,{}):continue
                edges.setdefault(key,{})[candidate]=direction
                added.append({'from':key,'to':candidate,'direction':direction,
                              'incoming_lane_pair':[before[0],neighbor],'outgoing_lane_pair':[after[0],other_after[0]],
                              'maximum_endpoint_heading_difference_deg':math.degrees(max(differences))})
    return RoadGraph(list(graph.nodes.values()),edges,tolerance=graph.tolerance),added
