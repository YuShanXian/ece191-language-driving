"""Single entry point for a stage. Failure never returns forced sideways motion."""

import math, time
from shapely.geometry import Point
from .scene import get_scene
from .routes import follow, trim
from .turns import turn
from .recovery import turnaround, reverse_history
from .reversing import reverse
from .lane_changes import lane_change
from .normalize import normalize
from .contract import validate_stage
from .intent import validate_intent

CONTROLS = {
    "continuous_drive",
    "resume",
    "set_speed",
    "speed_up",
    "slow_down",
    "stop",
    "hold_stopped",
    "emergency_stop",
    "cancel",
}
TURNS = {"turn_left", "turn_right", "u_turn", "go_straight"}
LANES = {"lane_change_left", "lane_change_right", "select_lane"}


def stage(action):
    return dict(
        action=action,
        source_clause=action.replace("_", " "),
        trigger="now",
        trigger_text="",
        trigger_value=None,
        target_text="",
        lane_reference="none",
        lane_number=None,
        completion_text="",
        constraints=[],
        travel_distance_m=10 if action == "reverse" else None,
        stop_at_end=action == "reverse",
        target_speed_mps=None,
    )


def plan(request):
    started = time.perf_counter()
    scene = get_scene(int(request["scene"]))
    state = request["state"]
    if not all(math.isfinite(v) for v in [*state["xy"], state["heading"], state.get("speed", 0)]):
        raise ValueError("Invalid vehicle pose")
    if request.get("op") == "follow":
        return {
            "status": "ready",
            "route": follow(scene, state),
            "completion_m": 0,
            "maneuver_start_m": 0,
        }
    validate_stage(request["stage"])
    st = normalize({"stages": [request["stage"]]})["stages"][0]
    action = st["action"]
    remaining = max(0, min(120, float(request.get("remaining", 20))))
    target = max(0.1, min(15, float(state.get("target_speed_mps", 20 / 3.6))))

    def result(**kwargs):
        return {
            **kwargs,
            "planning_ms": round((time.perf_counter() - started) * 1000, 2),
            "action": action,
            "origin": state["xy"],
        }

    def waiting(reason, diagnostics=None):
        try:
            route = validate_intent(follow(scene, state), 'keep_lane')
        except ValueError as e:
            if not scene.locate(state):
                return result(status="blocked", reason=str(e))
            route = None
        return result(status="waiting", reason=reason + " Stop before any unrequested turn; timeout continues to the next instruction.", route=route, retry_after_m=5.0, retry_after_s=1.0, diagnostics=diagnostics)

    if st.get("constraints") or st.get("target_text") or st.get("completion_text"):
        return result(
            status="unsupported",
            reason="This instruction includes an unresolved condition; it has been kept in the queue.",
        )
    if st.get("trigger") not in ("now", "after_previous", "intersection", "elapsed_time"):
        return result(
            status="unsupported", reason="This trigger needs additional scene information."
        )
    if st.get("trigger") == "elapsed_time" and request.get("elapsed", 0) < (
        st.get("trigger_value") or 0
    ):
        return waiting("Waiting for the requested delay")
    if st.get("trigger") == "intersection" and st.get("trigger_value") not in (None, 1):
        return result(
            status="unsupported", reason="Counting later intersections is not supported yet."
        )
    if action in CONTROLS:
        route = None
        if action in ("continuous_drive", "resume"):
            try:
                route = follow(scene, state)
            except ValueError as e:
                return result(status="blocked", reason=str(e))
        return result(status="control", control=st, route=route)
    if action in ("reverse", "reverse_continuous"):
        try:
            route = reverse(scene, state, float(st.get("travel_distance_m") or 10))
        except ValueError as e:
            # Do not drive forward to satisfy a reverse, and do not strand
            # later queued commands behind an unavailable distance.
            return result(status="waiting", route=None, retry_after_s=1,
                          reason=str(e) + '. Waiting at the current pose; timeout continues to the next instruction.')
        return result(
            status="ready",
            route=route,
            maneuver_start_m=0,
            completion_m=route["length"],
            speed_limit_mps=1.5,
            reason="Reverse along the current lane, following its bends without undoing earlier maneuvers.",
        )
    distance = st.get("travel_distance_m")
    stop = bool(st.get("stop_at_end"))
    if action == 'select_lane':
        located = scene.locate(state)
        if (located and located[0] in scene.topology.lateral_options(located[0], st)
                and scene.nodes[located[0]].baseline.distance(Point(state['xy'])) < .2):
            return result(status='control', control=st, route=None,
                reason='Already in the requested lane; no lane change is needed.')
    try:
        if action in ("go_straight", "keep_lane") and distance is not None:
            route = follow(scene, state)
            if route["length"] < distance:
                return waiting("Requested distance extends past the end of this lane")
            completion = float(distance)
            begin = 0
            tag = "distance"
        elif action == "keep_lane":
            route = follow(scene, state)
            completion = min(10, route["length"])
            begin = 0
            tag = "keep lane"
        elif action in TURNS:
            found = turn(scene, state, action)
            if not found:
                if action == 'u_turn':
                    if state.get('speed',0) > .02:
                        return result(status='braking',reason='Stopping to plan a turnaround with reverse assistance if needed.')
                    recovery = turnaround(scene,state,reverse_history)
                    if recovery:
                        return result(**recovery)
                return waiting(
                    "No matching maneuver on the reachable straight corridor."
                )
            route, begin, completion, tag = found
        elif action in LANES or action in ("pull_over", "park"):
            desired = (
                st
                if action in LANES
                else {
                    **st,
                    "action": "select_lane",
                    "lane_reference": "rightmost",
                    "lane_number": 1,
                }
            )
            diagnostics = {}
            found = lane_change(scene, state, desired, max_approach=1200, diagnostics=diagnostics)
            if not found:
                return waiting(
                    diagnostics['reason'] if diagnostics.get('code')=='opposing_lane_only' else
                    "Waiting for a continuous adjacent lane with enough room for the requested maneuver.", diagnostics
                )
            route, begin, completion, tag = found
            if action in ("pull_over", "park"):
                stop = True
                # Already in the requested curb lane: allow a braking distance in that lane.
                if completion < 0.05:
                    completion = min(route["length"], max(1.0, state.get("speed", 0) ** 2 / 3 + 1))
        else:
            return result(
                status="unsupported",
                reason=f"Action {action} is not supported by this map-only planner.",
            )
        # The waiting budget bounds finding a route, not traveling to its entry.
        # Once a connected maneuver exists, commit to it and show the approach
        # distance. Rejecting a 31-second approach on every 20-second retry made
        # a perfectly valid turn impossible forever.
        if distance is not None and action not in ("go_straight", "keep_lane"):
            completion += float(distance)
        if stop:
            route = trim(route, completion)
        validate_intent(route, action, route.get('permitted_maneuver'))
        return result(
            status="ready",
            route=route,
            maneuver_start_m=begin,
            completion_m=min(completion, route["length"]),
            stop_at_end=stop,
            route_source=tag,
            approach_seconds=begin / target,
            reason=(('Replan this junction from the current pose to the requested exit. ' if route.get('junction_replan') else '')
                    + (f'Prepare: {route["preparation"]["action"].replace("_"," ")} once before the junction. ' if route.get('preparation') else '')
                    + f'Continue {begin:.1f} m, then {action.replace("_"," ")}; follow the connected destination lane.'
                    + (' This is a continuous road bend, not a junction branch.'
                       if action == 'go_straight' and tag in scene.topology.by_connector and scene.topology.by_connector[tag].road_bend else '')),
            target_speed_mps=st.get("target_speed_mps"),
        )
    except ValueError as e:
        return waiting("Maneuver geometry rejected: " + str(e))
