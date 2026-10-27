from pathlib import Path
p=Path(__file__).parents[1]/'app/engine/routes.py'
s=p.read_text(encoding='utf-8');s=s[:s.index('def lane_change(')]+'''def corridor_line(scene, sections):
    points = []
    for key, start, end in sections:
        part = scene.section(key, start, end)
        if points and np.linalg.norm(points[-1] - part[0]) > 1:
            raise ValueError("Disconnected adjacent lane corridor")
        points.extend(part)
    points = clean(points)
    if len(points) < 2:
        raise ValueError("Lane corridor has ended")
    return LineString(points)


def lane_change(scene, state, stage, max_approach=200):
    located = scene.locate(state)
    if not located:
        return None
    lead, distance = [], 0.0
    for key, start, end in scene.topology.corridor(*located, limit=max_approach):
        node = scene.nodes[key]
        for target in scene.topology.lateral_options(key, stage):
            if target == key:
                return follow(scene, state), 0, 0, target
            required = max(25, abs((scene.nodes[target].lane_index or 1) - (node.lane_index or 1)) * 23)
            try:
                # A map node boundary is not a physical lane end. Construct both
                # adjacent continuous corridors before choosing maneuver length.
                source_sections = scene.continuation(key, start, required + 3)
                source_line = corridor_line(scene, source_sections)
                if source_line.length < required + 1:
                    continue
                p0 = source_line.interpolate(0)
                target_start = scene.nodes[target].baseline.project(p0)
                target_sections = scene.continuation(target, target_start, required + 30)
                target_line = corridor_line(scene, target_sections)
                source = np.array([source_line.interpolate(float(d)).coords[0] for d in np.linspace(0, required, int(required * 2) + 1)])
                target_s = np.array([target_line.project(Point(p)) for p in source])
                if np.min(np.diff(target_s)) < .05 or target_s[-1] > target_line.length - .5:
                    continue
                destination = np.array([target_line.interpolate(float(d)).coords[0] for d in target_s])
                # Two lanes that merge into the same centerline do not constitute
                # a completed lane change after the merge.
                if np.linalg.norm(destination[-1] - source[-1]) < 1.3:
                    continue
                u = np.linspace(0, 1, len(source));blend = 10*u**3 - 15*u**4 + 6*u**5
                curve = source + (destination-source)*blend[:,None]
                if not lead:
                    offset = np.asarray(state['xy']) - curve[0]
                    if np.linalg.norm(offset) > 2.2 or not node.polygon.buffer(.1).covers(Point(state['xy'])):
                        continue
                    curve += offset*(1-blend)[:,None]
                if not scene.graph.surface.covers(LineString(curve)):
                    continue
                lead_route = assemble(scene, lead, state) if lead else {'points':[state['xy']], 'segments':[]}
                prefix = lead_route['points']
                if np.linalg.norm(np.asarray(prefix[-1])-curve[0]) > .15:
                    continue
                prefix = list(prefix)+curve[1:].tolist()
                completion = float(arc(np.asarray(prefix))[-1])
                # Resolve the actual exit section of the destination corridor.
                remaining = float(target_s[-1])
                destination_key = target
                destination_offset = target_start
                for tk, ts, te in target_sections:
                    length = float(arc(scene.section(tk, ts, te))[-1])
                    if remaining <= length:
                        destination_key, destination_offset = tk, ts + remaining
                        break
                    remaining -= length
                route = assemble_tail(scene, [], scene.continuation(destination_key, destination_offset), prefix=prefix)
                route['segments'] = lead_route['segments'] + [{'node_id': key, 'start':distance, 'end':completion}] + route['segments']
                route['movements'] = scene.topology.describe(lead_route['segments']) + route.get('movements', [])
                route['lane_change'] = {'source': key, 'target': destination_key, 'start':distance, 'end':completion}
                return route, float(distance), completion, destination_key
            except ValueError:
                continue
        lead.append((key, start, end));distance += end-start
    return None
'''
p.write_text(s,encoding='utf-8')
