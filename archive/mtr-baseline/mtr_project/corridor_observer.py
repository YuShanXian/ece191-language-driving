"""Exploratory causal lane-change detection across short map connectors.

This extension does not alter the frozen candidate checks. It retains a prior
map corridor across a short localization gap, but never counts gap time as
settled maneuver evidence. Branching/unknown topology produces no event.
"""
from shapely.ops import unary_union
from trajectory_checks import footprint
from .observations import ManeuverObserver
from .stages import Observation


def unique_forward(edges, node):
    following=[key for key,kind in edges.get(node,{}).items() if kind=='forward']
    return following[0] if len(following)==1 else None


def forward_reaches(edges, source, target, limit=12):
    visited=set()
    for _ in range(limit):
        if source==target:return True
        if source is None or source in visited:return False
        visited.add(source);source=unique_forward(edges,source)
    return False


def terminal_lane(edges, kinds, node):
    for _ in range(8):
        if kinds.get(node)=='lane':return node
        if kinds.get(node)!='connector':return None
        node=unique_forward(edges,node)
    return None


def relation(edges,kinds,source,target):
    if forward_reaches(edges,source,target):return 'forward'
    a=terminal_lane(edges,kinds,source);b=terminal_lane(edges,kinds,target)
    if a is None or b is None:return None
    direction=edges.get(a,{}).get(b)
    return direction if direction in ('left','right') else None


def corridor_contains_body(graph,node,xy,heading,length,width,extension_m=12.):
    """Join only uniquely connected forward pieces around the current node."""
    if node not in graph.nodes:return False
    keys={node}
    for backwards in (False,True):
        current=node;distance=0.
        for _ in range(12):
            candidates=([a for a,links in graph.edges.items() if links.get(current)=='forward']
                        if backwards else [a for a,kind in graph.edges.get(current,{}).items() if kind=='forward'])
            if len(candidates)!=1 or candidates[0] not in graph.nodes or candidates[0] in keys:break
            current=candidates[0];keys.add(current);distance+=graph.nodes[current].baseline.length
            if distance>=extension_m:break
    polygon=unary_union([graph.nodes[key].polygon for key in keys]).buffer(graph.tolerance)
    return bool(polygon.covers(footprint(xy,heading,length,width)))


class CorridorManeuverObserver:
    def __init__(self,settle_seconds=.5,max_unknown_seconds=1.):
        if settle_seconds<=0 or max_unknown_seconds<=0:raise ValueError('Positive durations required')
        self.settle_seconds=settle_seconds;self.max_unknown_seconds=max_unknown_seconds
        self.base=ManeuverObserver({});self.anchor=None;self.last_localized=None;self.pending=None
        self.evidence=[];self.last_timestamp=None

    def update(self,state,edges,kinds,contains_body):
        self.base.edges=edges
        observed=self.base.update(state)  # validates times and measured values
        completed=[a for a in observed.completed_actions if not a.startswith('lane_change_')]
        if self.last_timestamp is not None and state.timestamp-self.last_timestamp>.3:
            self.anchor=None;self.pending=None
        self.last_timestamp=state.timestamp
        if self.last_localized is not None and state.timestamp-self.last_localized>self.max_unknown_seconds:
            self.anchor=None;self.pending=None
        if state.node is None:
            if self.pending:self.pending['since']=None
            return Observation(state.timestamp,state.x,state.y,state.speed,completed_actions=tuple(completed))
        if self.anchor is not None and self.anchor!=state.node:
            direction=relation(edges,kinds,self.anchor,state.node)
            if direction in ('left','right'):
                # Returning to the original corridor before settling cancels
                # the attempted change instead of reporting an opposite change.
                returns=bool(self.pending and forward_reaches(edges,self.pending['origin'],state.node))
                self.pending=None if returns else {'origin':self.anchor,'action':'lane_change_'+direction,
                                                   'since':None,'started_at':state.timestamp}
            elif direction!='forward':self.pending=None
        if self.pending:
            if contains_body(state.node) and not contains_body(self.pending['origin']):
                if self.pending['since'] is None:self.pending['since']=state.timestamp
                if state.timestamp-self.pending['since']>=self.settle_seconds-1e-9:
                    completed.append(self.pending['action'])
                    self.evidence.append({**self.pending,'completed_at':state.timestamp,'target':state.node})
                    self.pending=None
            else:self.pending['since']=None
        self.anchor=state.node;self.last_localized=state.timestamp
        return Observation(state.timestamp,state.x,state.y,state.speed,completed_actions=tuple(completed))
