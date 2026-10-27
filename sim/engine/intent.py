"""Validate the meaning of the complete route, including approach and tail."""
TURNS = {'turn_left', 'turn_right', 'u_turn'}


def validate_intent(route, action, permitted=None):
    turns = [m for m in route.get('movements', []) if m['action'] in TURNS and not m.get('road_bend')]
    for movement in turns:
        if movement['connector'] != permitted or movement['action'] != action:
            raise ValueError('Route contains an unrequested junction maneuver')
    if len(turns) > 1:
        raise ValueError('One instruction cannot permit multiple junction turns')
    route['intent'] = {'action': action, 'permitted_connector': permitted,
                       'unrequested_turns': 0, 'continuation': 'same_lane_corridor'}
    return route
