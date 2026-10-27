"""Road movements and neutral corridors, shared by every planning action.

A graph edge only means reachable. Prefer a straight exit when one exists;
otherwise a sole forward road continuation can bend. U-turn exits do not
compete with that continuation and are never selected automatically.
"""
from dataclasses import dataclass, replace
import math
from .continuity import connection_geometry, lane_rank_error, straight_rank_error


def direction(radians):
    degrees = math.degrees(radians)
    if abs(degrees) >= 150:
        return 'u_turn'
    if degrees > 30:
        return 'turn_left'
    if degrees < -30:
        return 'turn_right'
    return 'go_straight'


@dataclass(frozen=True)
class Movement:
    source: str
    connector: str
    target: str
    action: str
    angle: float
    lateral: float
    rank_error: int
    road_bend: bool = False


class RoadTopology:
    def __init__(self, graph):
        self.graph = graph
        self.by_lane = {}
        self.by_connector = {}
        self.forward = {}
        group_exits = {}
        group_targets = {}
        for key, node in graph.nodes.items():
            if node.kind != 'lane':
                continue
            for connector, relation in graph.edges.get(key, {}).items():
                if relation != 'forward':
                    continue
                for target, r in graph.edges.get(connector, {}).items():
                    end = graph.nodes[target]
                    if r == 'forward' and end.kind == 'lane':
                        angle, _ = connection_geometry(node, end)
                        if direction(angle) != 'u_turn':
                            group_exits.setdefault(node.lane_group,set()).add(end.lane_group)
                            group_targets.setdefault(node.lane_group,set()).add(target)
        rejoining_groups = {group for group, targets in group_targets.items()
                            if len(group_exits[group]) > 1 and self._same_rejoining_road(targets)}
        for key, node in graph.nodes.items():
            choices = [k for k,r in graph.edges.get(key, {}).items() if r == 'forward']
            if node.kind != 'lane':
                self.forward[key] = sorted(choices)
                continue
            movements = []
            for connector in choices:
                if graph.nodes[connector].kind != 'connector':
                    continue
                for target, relation in graph.edges.get(connector, {}).items():
                    exit_lane = graph.nodes[target]
                    if relation != 'forward' or exit_lane.kind != 'lane':
                        continue
                    angle, lateral = connection_geometry(node, exit_lane)
                    rank = (straight_rank_error(node, exit_lane, graph.lane_groups, graph.nodes, graph.edges)
                            if direction(angle) == 'go_straight' else lane_rank_error(node, exit_lane, graph.lane_groups))
                    bend = len(group_exits.get(node.lane_group, set())) == 1 and abs(angle) < math.radians(120)
                    move = Movement(key, connector, target, direction(angle), angle, lateral, rank, bend)
                    # A straight edge must not quietly substitute a lane change.
                    if move.action == 'go_straight' and abs(lateral) > 2.2 and rank > 0:
                        continue
                    movements.append(move)
                    self.by_connector[connector] = move
            movements.sort(key=lambda m:(m.rank_error, abs(m.lateral), m.connector))
            if (node.lane_group in rejoining_groups
                    and not any(m.action == 'go_straight' for m in movements)):
                # Some maps split a bend into a tiny lane and several native
                # paths that rejoin the same road. Separate group IDs alone
                # do not make this a new intersection. Keep one correspondence;
                # alternatives must not become implicit lane changes.
                bends = [m for m in movements if m.rank_error == 0
                         and abs(m.angle) < math.radians(120)
                         and not m.connector.startswith('J_')]
                if bends and (len(bends) == 1 or abs(bends[1].lateral)-abs(bends[0].lateral) > 1.5):
                    chosen = replace(bends[0], road_bend=True)
                    movements = [chosen if m.connector == chosen.connector else m for m in movements]
                    self.by_connector[chosen.connector] = chosen
            self.by_lane[key] = movements
            straight = [m for m in movements if m.action == 'go_straight']
            if not straight:
                straight = [m for m in movements if m.road_bend and m.rank_error == 0]
            if straight:
                nearest = min(abs(m.lateral) for m in straight)
                straight = [m for m in straight if abs(m.lateral) <= nearest + 1.5]
            self.forward[key] = [m.connector for m in straight]

        # Reverse is a lane query, not a traversal of the vehicle's history.
        # Resolve the incoming correspondence independently: at a merge, a
        # straight continuation wins over a side road that bends into this lane.
        incoming = {}
        for moves in self.by_lane.values():
            for m in moves:
                if m.action != 'u_turn':
                    incoming.setdefault(m.target, []).append(m)
        self.backward = {}
        for target, moves in incoming.items():
            straight = [m for m in moves if m.action == 'go_straight' and m.rank_error == 0]
            if straight:
                candidates = straight
            else:
                bends = [m for m in moves if m.road_bend and m.rank_error == 0]
                groups = {graph.nodes[m.source].lane_group for m in bends}
                candidates = bends if len(groups) == 1 else []
            if not candidates:
                continue
            # Prefer an actual mapped correspondence. Synthetic missing links
            # can fan several entry lanes into one exit; following them back
            # indiscriminately would recreate an unrequested lane change.
            native = [m for m in candidates if not m.connector.startswith('J_')]
            candidates = native or candidates
            candidates.sort(key=lambda m: (abs(m.lateral), m.connector))
            best = candidates[0]
            if len(candidates)>1 and abs(abs(candidates[1].lateral)-abs(best.lateral)) < .25:
                continue  # Ambiguous split: stop instead of choosing a branch.
            self.backward[target] = best.connector
        for connector, m in self.by_connector.items():
            if self.is_neutral(m) and m.rank_error == 0:
                self.backward[connector] = m.source

    def _same_rejoining_road(self, targets):
        """Prove a short, same-direction native split rejoins one exact lane.

        Direction alone is insufficient: parallel roads or an unresolved fork
        must still require a command. Ignore U-turns, require native mapped
        links, and reject further turns before the common downstream lane.
        """
        from .geometry import tangent, angle_diff
        headings = [tangent(self.graph.nodes[k].baseline,
                            self.graph.nodes[k].baseline.coords[0]) for k in targets]
        if any(abs(angle_diff(a, b)) > math.radians(15) for a in headings for b in headings):
            return False
        joins = []
        for key in targets:
            lane = self.graph.nodes[key]
            destinations = set()
            for connector, rel in self.graph.edges.get(key, {}).items():
                if rel != 'forward' or not connector.startswith('C'):
                    continue
                connection = self.graph.nodes[connector]
                if lane.baseline.length + connection.baseline.length > 60:
                    continue
                for target, relation in self.graph.edges.get(connector, {}).items():
                    end = self.graph.nodes[target]
                    if relation != 'forward' or end.kind != 'lane':
                        continue
                    action = direction(connection_geometry(lane, end)[0])
                    if action == 'u_turn':
                        continue
                    if action != 'go_straight':
                        return False
                    destinations.add(target)
            joins.append(destinations)
        return bool(joins and set.intersection(*joins))

    def reverse_corridor(self, key, start, limit):
        """Yield backward sections of the current lane, stopping at ambiguity."""
        seen, distance = set(), 0.0
        while key not in seen and distance < limit:
            move = self.by_connector.get(key)
            if move and not self.is_neutral(move):
                break
            seen.add(key)
            end = max(0.0, start - (limit-distance))
            if start-end > 1e-5:
                yield (key, start, end)
                distance += start-end
            if end > 0 or key not in self.backward:
                break
            key = self.backward[key]
            start = self.graph.nodes[key].baseline.length

    def options(self, key, action):
        candidates = self.by_lane.get(key, [])
        if key in self.by_connector:
            candidates = [self.by_connector[key]]
        matches = [m for m in candidates if m.action == action]
        if action == 'go_straight' and not matches:
            matches = [m for m in candidates if m.road_bend and m.rank_error == 0]
        if action in ('turn_left', 'turn_right', 'u_turn'):
            # Only compare movements reachable from this very lane. A nearby
            # native curve in another lane is not permission to change lanes.
            matches = sorted(matches, key=lambda m: (
                m.connector.startswith('J_'), m.rank_error, abs(m.lateral), m.connector))
        return matches

    def corridor(self, key, start=0, limit=2800):
        """Follow a lane without permitting a turn or revisiting a node."""
        seen = set()
        distance = 0.0
        while key not in seen and distance < limit:
            seen.add(key)
            length = self.graph.nodes[key].baseline.length
            end = min(length, start + limit - distance)
            yield (key, start, end)
            distance += end - start
            if end < length:
                break
            nexts = self.forward.get(key, [])
            if not nexts:
                break
            key, start = nexts[0], 0

    def lateral_options(self, key, stage):
        """Map lateral lane identity across a segment boundary.

        A connector is a section of a lane, not a reason to lose its neighbors.
        Match both its entry and exit lanes: nearby crossing/merging connectors
        are not adjacent lanes, even when they share a broad road surface.
        """
        node = self.graph.nodes[key]
        movement = self.by_connector.get(key)
        if node.kind != 'lane':
            if not movement or not self.is_neutral(movement):
                return []
            source = movement.source
        else:
            source = key
        lane = self.graph.nodes[source]
        if stage['action'] == 'select_lane':
            lanes = sorted(self.graph.lane_groups[lane.lane_group], key=lambda n:n.lane_index or 0,
                           reverse=stage.get('lane_reference') == 'rightmost')
            index = (stage.get('lane_number') or 1) - 1
            targets = [lanes[index].key] if 0 <= index < len(lanes) else []
        else:
            relation = 'left' if stage['action'] == 'lane_change_left' else 'right'
            targets = [k for k,r in self.graph.edges.get(source, {}).items() if r == relation]
        if node.kind == 'lane':
            return targets
        candidates = []
        for target in targets:
            delta = (self.graph.nodes[target].lane_index or 0) - (lane.lane_index or 0)
            for other in self.by_lane.get(target, []):
                end = self.graph.nodes[movement.target]
                other_end = self.graph.nodes[other.target]
                if (self.is_neutral(other) and other.action == movement.action
                        and end.lane_group == other_end.lane_group
                        and (other_end.lane_index or 0) - (end.lane_index or 0) == delta):
                    candidates.append(other.connector)
        return candidates

    @staticmethod
    def is_neutral(movement):
        return movement.action == 'go_straight' or (movement.road_bend and movement.rank_error == 0)

    def describe(self, segments):
        return [dict(connector=x['node_id'], source=self.by_connector[x['node_id']].source,
                     target=self.by_connector[x['node_id']].target,
                     action=self.by_connector[x['node_id']].action,
                     road_bend=self.by_connector[x['node_id']].road_bend,
                     start=x['start'], end=x['end'])
                for x in segments if x['node_id'] in self.by_connector]
