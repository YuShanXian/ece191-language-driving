"""One-time, reviewable source transformation for the v29 refactor."""
from pathlib import Path
root=Path(__file__).parents[1]
p=root.parents[1]/'sim/engine/routes.py'
s=p.read_text()
a=s.index('def turn('); b=s.index('\ndef lane_change(', a)
s=s[:a]+'''def turn(scene, state, action):
    located = scene.locate(state)
    if not located:
        return None
    approach = []
    distance = 0.0
    for key, start, end in scene.topology.corridor(*located, limit=1200):
        node = scene.nodes[key]
        for movement in scene.topology.options(key, action):
            connector, target = movement.connector, movement.target
            lead = approach + ([] if node.kind == "connector" else [(key, start, end)])
            begin = distance + (0 if node.kind == "connector" else end - start)
            connector_start = start if key == connector else 0
            required = lead + [(connector, connector_start, scene.nodes[connector].baseline.length),
                               (target, 0, min(8, scene.nodes[target].baseline.length))]
            completion = begin + scene.nodes[connector].baseline.length - connector_start + min(8, scene.nodes[target].baseline.length)
            tail = scene.continuation(target, min(8, scene.nodes[target].baseline.length))
            try:
                route = assemble_tail(scene, required, tail, state)
            except ValueError:
                continue
            route["permitted_maneuver"] = connector
            return route, float(begin), float(completion), connector
        approach.append((key, start, end))
        distance += end - start
    return None


def assemble_tail(scene, required, tail, pose=None, prefix=None):
    """A defective remote tail cannot invalidate an executable local maneuver."""
    try:
        return assemble(scene, required + tail, pose, prefix)
    except ValueError:
        # Validate the required maneuver first; it must never be truncated.
        valid = assemble(scene, required, pose, prefix)
        for i in range(1, len(tail) + 1):
            try:
                valid = assemble(scene, required + tail[:i], pose, prefix)
            except ValueError:
                valid["boundary_reason"] = "Mapped continuation has incompatible geometry"
                break
        return valid

''' + s[b:]
s=s.replace('"stop_at_end": True,','"stop_at_end": True,\n        "movements": scene.topology.describe(markers),')
s=s.replace('route = assemble(\n                        scene, scene.continuation(target, float(target_s[-1])), prefix=prefix\n                    )','route = assemble_tail(\n                        scene, [], scene.continuation(target, float(target_s[-1])), prefix=prefix\n                    )')
s=s.replace('route["segments"].insert(0, {"node_id": key, "start": 0.0, "end": completion})','lead_markers = assemble(scene, lead, state)["segments"] if lead else []\n                    route["segments"] = lead_markers + [{"node_id": key, "start": float(distance), "end": completion}] + route["segments"]\n                    route["movements"] = scene.topology.describe(route["segments"])')
p.write_text(s)
# Remove the retired, conflicting implicit-turn selector entirely.
p=root.parents[1]/'sim/engine/continuity.py';s=p.read_text();p.write_text(s[:s.index('\ndef forward_choices')])
for p in [* (root.parents[1]/'sim').rglob('*.js'), *(root.parents[1]/'sim').rglob('*.cjs'), root/'deploy.py']:
 s=p.read_text();p.write_text(s.replace('refactor-v28','refactor-v29'))
