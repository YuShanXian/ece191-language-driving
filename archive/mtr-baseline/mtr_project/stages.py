"""Causal stage progression driven by measured states, never by candidate forecasts."""
from dataclasses import dataclass, field
import math

@dataclass(frozen=True)
class Observation:
    timestamp: float
    x: float
    y: float
    speed: float
    source: str = 'recorded_observation'
    events: tuple = ()
    completed_actions: tuple = ()

@dataclass
class StageMachine:
    program: dict
    capabilities: frozenset = frozenset()
    index: int = 0
    state: str = 'uninitialized'
    history: list = field(default_factory=list)
    _last: Observation | None = None
    _start_time: float | None = None
    _active_time: float | None = None
    _distance: float = 0.
    _events: dict = field(default_factory=dict)
    _seen_event_ids: set = field(default_factory=set)

    def __post_init__(self):
        if self.program.get('status')!='parsed' or not self.program.get('stages'):
            raise ValueError('A fully parsed nonempty program is required')
        required=set(self.program.get('required_grounding_capabilities',[]))
        self.state='blocked_missing_grounding' if not required.issubset(self.capabilities) else 'waiting'

    def update(self,obs):
        if obs.source not in ('recorded_observation','live_observation','synthetic_test_observation'):
            raise ValueError('Forecasts cannot advance instruction stages')
        if not all(math.isfinite(v) for v in (obs.timestamp,obs.x,obs.y,obs.speed)) or obs.speed<0:
            raise ValueError('Invalid observation')
        if self._last is not None and obs.timestamp<=self._last.timestamp:
            raise ValueError('Observations must have strictly increasing timestamps')
        for event in obs.events:
            if len(event)!=2 or not all(isinstance(x,str) and x for x in event):
                raise ValueError('Event requires kind and unique map-object ID')
        if self._last is not None:
            delta=math.hypot(obs.x-self._last.x,obs.y-self._last.y)
            if delta/(obs.timestamp-self._last.timestamp)>60:
                raise ValueError('Implausible position discontinuity')
            self._distance+=delta
        self._last=obs
        if self._start_time is None:self._start_time=obs.timestamp
        if self.state in ('completed','blocked_missing_grounding'):return self.snapshot()
        for event in obs.events:
            # Caller must provide grounded event kind and stable object identity.
            if event not in self._seen_event_ids:
                self._seen_event_ids.add(event)
                self._events[event[0]]=self._events.get(event[0],0)+1
        stage=self.program['stages'][self.index]
        if self.state=='waiting':
            trigger=stage['trigger'];kind=trigger['kind']
            satisfied=(kind=='now' or
                       kind=='elapsed_time' and obs.timestamp-self._start_time>=trigger['threshold'] or
                       kind=='distance' and self._distance>=trigger['threshold'] or
                       kind=='observed_event_count' and self._events.get(trigger['event'],0)>=trigger['threshold'])
            if satisfied:
                self.state='active';self._active_time=obs.timestamp
                self.history.append({'stage':self.index,'event':'activated','timestamp':obs.timestamp})
        elif self.state=='active' and obs.timestamp>self._active_time and stage['action'] in obs.completed_actions:
            self.history.append({'stage':self.index,'event':'observed_complete','timestamp':obs.timestamp})
            self.index+=1
            if self.index==len(self.program['stages']):self.state='completed'
            else:
                self.state='waiting';self._start_time=obs.timestamp;self._distance=0.;self._events={}
                # Retain globally seen event IDs: the same light is not a new light
                # just because a later stage started. A future revisit needs a new
                # pass-event identity supplied by the observation adapter.
        return self.snapshot()

    def snapshot(self):
        return {'state':self.state,'stage_index':self.index,
                'action':self.program['stages'][self.index]['action'] if self.state=='active' else None,
                'observed_distance_m':self._distance,'history':list(self.history)}
