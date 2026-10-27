"""Maneuver completion from measured states and explicit road transitions.

The detector never reads a selected candidate. Map nodes supplied by a causal
localization step; ambiguous/missing nodes reset pending completion evidence.
"""
from dataclasses import dataclass
import math
from .stages import Observation

@dataclass(frozen=True)
class MeasuredState:
    timestamp: float
    x: float
    y: float
    heading: float
    speed: float
    node: str | None
    node_kind: str | None
    body_inside_node: bool

class ManeuverObserver:
    def __init__(self, edges, settle_seconds=.5):
        if settle_seconds<=0:raise ValueError('Positive settling duration required')
        self.edges=edges;self.settle_seconds=settle_seconds
        self.previous=None;self.stop_since=None;self.stop_reported=False
        self.pending_change=None;self.turn_entry=None;self.pending_turn=None

    def update(self,state):
        values=(state.timestamp,state.x,state.y,state.heading,state.speed)
        if not all(math.isfinite(v) for v in values) or state.speed<0:raise ValueError('Invalid measured state')
        prior=self.previous
        if prior is not None and state.timestamp<=prior.timestamp:raise ValueError('Time must increase')
        if prior is not None and state.timestamp-prior.timestamp>.3:
            self.pending_change=None;self.turn_entry=None;self.pending_turn=None;self.stop_since=None
            prior=None
        completed=[]
        if state.speed<=.3:
            if self.stop_since is None:self.stop_since=state.timestamp
            if state.timestamp-self.stop_since>=self.settle_seconds and not self.stop_reported:
                completed.append('stop');self.stop_reported=True
        else:self.stop_since=None;self.stop_reported=False
        if state.node is None:
            self.pending_change=None;self.turn_entry=None;self.pending_turn=None
        elif prior is not None and prior.node is not None:
            relation=self.edges.get(prior.node,{}).get(state.node)
            if prior.node!=state.node and relation in ('left','right'):
                self.pending_change={'target':state.node,'action':'lane_change_'+relation,'settled_since':None}
            if prior.node_kind=='lane' and state.node_kind=='connector' and relation=='forward':
                self.turn_entry={'heading':prior.heading,'timestamp':state.timestamp}
            if prior.node_kind=='connector' and state.node_kind=='lane':
                if relation=='forward' and self.turn_entry is not None:
                    angle=math.atan2(math.sin(state.heading-self.turn_entry['heading']),math.cos(state.heading-self.turn_entry['heading']))
                    if abs(angle)>=math.radians(30):
                        self.pending_turn={'target':state.node,'action':'turn_left' if angle>0 else 'turn_right','settled_since':None}
                self.turn_entry=None
            if prior.node!=state.node and relation is None:
                self.pending_change=None;self.turn_entry=None;self.pending_turn=None
        for field in ('pending_change','pending_turn'):
            pending=getattr(self,field)
            if pending is None:continue
            if state.node!=pending['target']:
                setattr(self,field,None);continue
            if not state.body_inside_node:pending['settled_since']=None;continue
            if pending['settled_since'] is None:pending['settled_since']=state.timestamp
            if state.timestamp-pending['settled_since']>=self.settle_seconds-1e-9:
                completed.append(pending['action']);setattr(self,field,None)
        self.previous=state
        return Observation(state.timestamp,state.x,state.y,state.speed,completed_actions=tuple(completed))
