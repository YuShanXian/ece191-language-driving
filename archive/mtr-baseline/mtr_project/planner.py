"""Connect explicit language, measured progress, and screened MTR candidates."""
import math
from .language import parse_instruction
from .stages import StageMachine
from language_selector import action_matches

class OfflinePlanner:
    def __init__(self,instruction,capabilities=frozenset()):
        self.instruction=instruction
        self.program=parse_instruction(instruction)
        self.machine=StageMachine(self.program,capabilities) if self.program['status']=='parsed' else None

    def step(self,observation,candidates):
        # No future reference, recorded maneuver label, or evaluation metric is
        # accepted in this interface. Completion comes from the observation adapter.
        if self.machine is None:
            return {'status':'unsupported_instruction','program':self.program,'candidate':None}
        state=self.machine.update(observation)
        if state['state']!='active':
            return {'status':state['state'],'program':self.program,'stage':state,'candidate':None}
        identifiers=[r['candidate'] for r in candidates]
        if len(identifiers)!=len(set(identifiers)):raise ValueError('Duplicate candidate IDs')
        for row in candidates:
            if not math.isfinite(row['score']) or row['score']<0:raise ValueError('Invalid candidate score')
        eligible=[r for r in candidates if r.get('passes_current_checks') is True
                  and action_matches(r,state['action'],observation.speed)]
        chosen=max(eligible,key=lambda r:(r['score'],-r['candidate'])) if eligible else None
        return {'status':'selected_conditionally' if chosen else 'no_matching_candidate',
                'program':self.program,'stage':state,'candidate':chosen['candidate'] if chosen else None,
                'matching_candidates':[r['candidate'] for r in eligible],
                'scope':'Offline proposal under explicit limited screens. No vehicle actuation.'}
