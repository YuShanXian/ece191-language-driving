"""Explicit action/trigger compiler. No LLM and no silent clause dropping.

Parsed means represented, not grounded or safe to execute. Named objects,
destinations, lane-purpose references and unrecognised conditions are rejected.
"""
import re

ORDINALS={'first':1,'second':2,'third':3,'fourth':4,'fifth':5,'next':1}
ACTIONS=[
    (r'(?:merge|change|move|get|switch)(?: over)? (?:to|into) (?:the )?(left|right)(?:-hand)? lane', 'lane_change'),
    (r'(?:merge|change|move|switch) (?:one|1) lane (?:to (?:the )?)?(left|right)', 'lane_change'),
    (r'change lanes? to (?:the )?(left|right)', 'lane_change'),
    (r'make (?:a )?turn (left|right)', 'turn'),
    (r'turn (left|right)', 'turn'),
    (r'make (?:a )?(left|right)(?: turn)?', 'turn'),
    (r'(?:keep|stay in|maintain|remain in) (?:the |your |current |the current )?lane', 'keep_lane'),
    (r'(?:go|continue|keep going|drive|proceed) straight(?: ahead)?', 'go_straight'),
    (r'(?:slow down|reduce (?:your )?speed|decelerate)', 'slow_down'),
    (r'(?:stop|come to a (?:complete )?stop)', 'stop'),
    (r'(?:remain stopped|stay stopped)', 'hold_stopped'),
]

def action_for(text):
    for pattern,kind in ACTIONS:
        match=re.fullmatch(pattern,text)
        if match:
            return kind+'_'+match.group(1) if kind in ('lane_change','turn') else kind
    return None

def parse_condition(text):
    distance=re.fullmatch(r'after (\d+(?:\.\d+)?) (meters?|metres?|m|seconds?|s)',text)
    if distance:
        amount=float(distance.group(1));unit=distance.group(2)
        if not 0<amount<=10000:return None
        return {'kind':'distance' if unit.startswith('m') else 'elapsed_time','threshold':amount,
                'reference':'stage_activation','requires':[]}
    passed=re.fullmatch(r'after (?:passing|you pass) (?:the )?(first|second|third|fourth|fifth|next|[1-5](?:st|nd|rd|th)?) (traffic light|stoplight|intersection)',text)
    if passed:
        number=ORDINALS.get(passed.group(1)) or int(re.sub(r'\D','',passed.group(1)))
        return {'kind':'observed_event_count','event':'passed_'+('traffic_light' if passed.group(2) in ('traffic light','stoplight') else 'intersection'),
                'threshold':number,'reference':'stage_activation','requires':['grounded_unique_map_events']}
    if re.fullmatch(r'(?:at|when you reach) (?:the )?(?:next|upcoming) intersection',text):
        return {'kind':'observed_event_count','event':'reached_intersection','threshold':1,
                'reference':'stage_activation','requires':['grounded_unique_map_events']}
    if text in ('when the light turns green','when the traffic light turns green'):
        return {'kind':'observed_event_count','event':'relevant_light_green','threshold':1,
                'reference':'stage_activation','requires':['route_relevant_traffic_light']}
    return None

def parse_instruction(text):
    if not isinstance(text,str) or not text.strip():return {'status':'unsupported','reason':'empty_instruction','stages':[]}
    normalized=re.sub(r'\s+',' ',text.strip().lower()).strip(' .!')
    normalized=re.sub(r'^please\s+','',normalized)
    # Exact segmentation only. "and" can express a constraint, so is not dropped.
    clauses=re.split(r'\s*[,;]?\s+(?:and then|then|after that)\s+|[.;]\s+',normalized)
    if len(clauses)>8:return {'status':'unsupported','reason':'too_many_stages','stages':[]}
    stages=[]
    for raw in clauses:
        clause=raw.strip(' ,.!')
        condition={'kind':'now','requires':[]};body=clause
        # Prefix trigger has an explicit comma; suffix trigger has a clear keyword.
        if ',' in clause:
            prefix,body=clause.split(',',1);condition=parse_condition(prefix.strip())
            if condition is None:return {'status':'unsupported','reason':'unsupported_trigger','clause':raw,'stages':[]}
            body=body.strip()
        else:
            suffix=re.search(r'\s+(after |at |when )',clause)
            if suffix:
                body=clause[:suffix.start()];condition=parse_condition(clause[suffix.start():].strip())
                if condition is None:return {'status':'unsupported','reason':'unsupported_trigger','clause':raw,'stages':[]}
        action=action_for(body)
        if action is None:return {'status':'unsupported','reason':'unsupported_action_or_constraint','clause':raw,'stages':[]}
        stages.append({'action':action,'trigger':condition,'source_clause':raw})
    for stage in stages[:-1]:
        if stage['action'] in ('keep_lane','go_straight','slow_down','hold_stopped'):
            return {'status':'unsupported','reason':'missing_stage_completion_condition','stages':[]}
    requirements=sorted({x for stage in stages for x in stage['trigger']['requires']})
    return {'status':'parsed','parser':'explicit_grammar_v2','stages':stages,
            'required_grounding_capabilities':requirements,
            'runnable_without_external_events':not requirements,
            'scope':'Complete supported clauses only. Parsed triggers still require validated observations.'}
