"""Conservative description of exact-current signals along frozen candidate nodes."""
import re
from collections import defaultdict


def map_ids(value):
    if value is None or str(value).strip()=='':return []
    values=[s.strip() for s in str(value).split(',') if s.strip()]
    if any(not re.fullmatch(r'\d+',s) for s in values):raise ValueError('Unexpected map ID list')
    return list(dict.fromkeys(str(int(s)) for s in values))


def signal_observations(rows):
    grouped=defaultdict(list)
    for connector,status in rows:
        identifier=str(connector)
        if not re.fullmatch(r'\d+',identifier):raise ValueError('Invalid observed connector ID')
        grouped[str(int(identifier))].append(str(status).lower())
    result={}
    for connector,values in grouped.items():
        distinct=sorted(set(values))
        classification=distinct[0] if len(distinct)==1 and distinct[0] in ('red','yellow','green','unknown') else 'ambiguous' if len(distinct)>1 else 'unknown'
        result[connector]={'classification':classification,'raw_statuses':values,'row_count':len(values),'conflicting':len(distinct)>1}
    return result


def describe_route(route,observations,connectors,dt=.1):
    if not route.get('matched'):
        return {'status':'unmatched_route','connector_visits':[],'future_entry_signal_classes':[],
                'has_predicted_connector_entry':False,'all_future_entries_currently_green':False}
    nodes=route.get('node_sequence',[])
    if not nodes or not all(isinstance(n,str) and re.fullmatch(r'[LC]\d+',n) for n in nodes):
        raise ValueError('Malformed matched route nodes')
    visits=[]
    for i,node in enumerate(nodes):
        if not node.startswith('C') or (i>0 and node==nodes[i-1]):continue
        identifier=str(int(node[1:]));known=connectors.get(identifier)
        signal=observations.get(identifier,{'classification':'unobserved','raw_statuses':[],'row_count':0,'conflicting':False})
        visits.append({'connector_id':identifier,'kind':'already_occupied_at_anchor' if i==0 else 'predicted_connector_entry',
            'previous_node':None if i==0 else nodes[i-1], 'first_sample_time_s':i*dt,
            'center_node_transition_interval_s':None if i==0 else [(i-1)*dt,i*dt],
            'current_signal':signal,'map_context':known,'map_connector_resolved':known is not None})
    future=[v for v in visits if v['kind']=='predicted_connector_entry']
    classes=sorted({v['current_signal']['classification'] for v in future})
    return {'status':'described','connector_visits':visits,'future_entry_signal_classes':classes,
        'has_predicted_connector_entry':bool(future),'all_future_entries_currently_green':bool(future) and all(v['current_signal']['classification']=='green' for v in future)}
