"""Conservative controlled-language baseline for offline candidate ranking.

Unsupported content is rejected, never silently dropped. No API calls or LLM.
"""
import re
from dataclasses import dataclass

RULES=[
    (r'(?:merge|change|move)(?: over)? (?:to|into) (?:the )?(left|right)(?:-hand)? lane',None),
    (r'change lanes? to (?:the )?(left|right)',None),
    (r'(?:keep|stay in|maintain) (?:the |your |current )?lane','keep_lane'),
    (r'(?:go|continue|keep going) straight','go_straight'),
    (r'(?:slow down|reduce (?:your )?speed)','slow_down'),
    (r'(?:stop|come to a stop)','stop'),
    (r'(?:remain stopped|stay stopped)','hold_stopped'),
    (r'turn (left|right)', 'turn'),
]

def parse_instruction(text):
    if not isinstance(text,str) or not text.strip():return {'status':'unsupported','reason':'empty_instruction'}
    normalized=re.sub(r'\s+',' ',text.strip().lower()).strip(' .!')
    clauses=re.split(r'\s*[,;]?\s+then\s+',normalized)
    if len(clauses)>3:return {'status':'unsupported','reason':'too_many_stages'}
    stages=[]
    for clause in clauses:
        action=None
        for pattern,kind in RULES:
            match=re.fullmatch(pattern,clause)
            if match:
                action=('lane_change_'+match.group(1)) if kind is None else ('turn_'+match.group(1) if kind=='turn' else kind)
                break
        if action is None:return {'status':'unsupported','reason':'unsupported_or_grounded_clause','clause':clause}
        stages.append({'action':action,'trigger':'now' if not stages else 'previous_stage_observed_complete'})
    for stage in stages[:-1]:
        if stage['action'] in ('keep_lane','go_straight','slow_down','hold_stopped'):
            return {'status':'unsupported','reason':'missing_stage_completion_trigger'}
    return {'status':'parsed','parser':'controlled_grammar_v1','stages':stages,
            'note':'Only the entire supported clause is accepted; scene-grounded references need a separate resolver.'}

@dataclass
class StageTracker:
    stages:list
    active_index:int=0
    completed:bool=False

    def observe(self,observed_completed_actions):
        # Caller must derive these events from observed vehicle state, never a selected prediction.
        if self.completed:return
        if self.stages[self.active_index]['action'] in observed_completed_actions:
            self.active_index+=1
            if self.active_index==len(self.stages):self.completed=True

    def active(self):return None if self.completed else self.stages[self.active_index]['action']

def action_matches(row,action,current_speed):
    route=row['route']
    if not route.get('matched'):return False
    changes=route.get('lane_changes',[]);turns=route.get('turns',[])
    if action.startswith('lane_change_'):
        return len(changes)==1 and changes[0]['action']==action and changes[0].get('settled_for_last_half_second',False) and not turns
    if action.startswith('turn_'):
        return len(turns)==1 and turns[0]['action']==action and not changes
    if action in ('keep_lane','go_straight'):
        return not changes and not turns and (action=='keep_lane' or row['motion']['end_speed_mps']>1.)
    if action=='stop':return row['motion'].get('end_max_speed_mps',float('inf'))<=.3 and not changes and not turns
    if action=='hold_stopped':
        return current_speed<=.3 and row['motion']['peaks']['speed_mps']<=.3 and row['motion']['max_displacement_m']<=.5 and not changes and not turns
    if action=='slow_down':return current_speed>=2 and row['motion']['end_speed_mps']<=current_speed-2 and not changes and not turns
    return False

def select(instruction,rows,current_speed,stage_index=0):
    parsed=parse_instruction(instruction)
    if parsed['status']!='parsed':return {'status':'unsupported_instruction','parse':parsed,'selected_candidate':None}
    if not 0<=stage_index<len(parsed['stages']):return {'status':'invalid_stage','selected_candidate':None}
    action=parsed['stages'][stage_index]['action']
    eligible=[r for r in rows if r['passes_current_checks']]
    matching=[r for r in eligible if action_matches(r,action,current_speed)]
    base=max(rows,key=lambda r:r['score'])
    filtered=max(eligible,key=lambda r:r['score']) if eligible else None
    chosen=max(matching,key=lambda r:r['score']) if matching else None
    return {'status':'selected_conditionally' if chosen else 'no_matching_candidate',
        'parse':parsed,'active_stage_index':stage_index,'active_action':action,
        'selected_candidate':chosen['candidate'] if chosen else None,
        'matching_candidates':[r['candidate'] for r in matching],
        'baseline_raw_highest_score':base['candidate'],
        'baseline_checked_highest_score':filtered['candidate'] if filtered else None,
        'selected_model_score':chosen['score'] if chosen else None,
        'scope':'Offline choice under limited checks; not a vehicle command or full safety guarantee.'}
