"""Turn intent includes a single, explicit preparatory merge when necessary.

Keep lane preparation before the junction and on its paired incoming lanes.
Never follow a completed turn with an unrequested lateral correction.
"""
import numpy as np
from .routes import turn as direct_turn, assemble, assemble_tail
from .lane_changes import transition
from .geometry import arc
from .junction_replan import replan


def turn(scene, state, action):
    redirected = replan(scene, state, action)
    if redirected:
        return redirected
    direct = direct_turn(scene, state, action)
    if action == 'go_straight' or direct and not direct[3].startswith('J_'):
        return direct
    located = scene.locate(state)
    if not located:
        return direct
    lead, distance = [], 0.0
    for key, start, end in scene.topology.corridor(*located, limit=1200):
        node = scene.nodes[key]
        if node.kind == 'lane':
            side = 'lane_change_right' if action == 'turn_right' else 'lane_change_left'
            st = {'action': side}
            for target in scene.topology.lateral_options(key, st):
                for movement in scene.topology.options(target, action):
                    if movement.connector.startswith('J_'):
                        continue
                    available = min(end-start, scene.nodes[target].baseline.length-start)-1.5
                    if available < 15:
                        continue
                    try:
                        curve, end_key, offset, proof = transition(
                            scene, state if not lead else None, key, start, target, st,
                            length=min(25, available))
                        if end_key != target:
                            continue
                        lead_route = assemble(scene, lead, state) if lead else {'points':[state['xy']], 'segments':[]}
                        prefix = lead_route['points'] + curve[1:].tolist()
                        merge_end = float(arc(np.asarray(prefix))[-1])
                        connector = movement.connector
                        target_lane = movement.target
                        begin = merge_end + scene.nodes[target].baseline.length-offset
                        completion = begin + scene.nodes[connector].baseline.length + min(8,scene.nodes[target_lane].baseline.length)
                        required = [(target,offset,scene.nodes[target].baseline.length),
                                    (connector,0,scene.nodes[connector].baseline.length),
                                    (target_lane,0,min(8,scene.nodes[target_lane].baseline.length))]
                        route = assemble_tail(scene, required,
                            scene.continuation(target_lane,min(8,scene.nodes[target_lane].baseline.length)), prefix=prefix)
                        route['segments'] = lead_route['segments'] + [dict(node_id=key,start=distance,end=merge_end)] + route['segments']
                        route['movements'] = scene.topology.describe(lead_route['segments']) + route['movements']
                        route['permitted_maneuver'] = connector
                        route['geometry_source'] = 'prepared_mapped_turn'
                        route['preparation'] = dict(action=side,start=distance,end=merge_end,**proof)
                        return route,float(begin),float(completion),connector
                    except ValueError:
                        continue
        lead.append((key,start,end)); distance += end-start
        if direct and distance > direct[1]:
            break
    return direct
