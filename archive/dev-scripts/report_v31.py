from pathlib import Path
import json,hashlib,math
root=Path(__file__).parents[1]; out=root/'results'
gate=json.loads((out/'browser-gate.json').read_text())
aux=json.loads((out/'auxiliary-audit.json').read_text())
assert gate['passed'] and gate['completed']==13 and aux['passed']
log=Path('historical-project/runs/project-v3/refactor-v31')
events=[json.loads(l) for l in (log/'events.jsonl').read_text().splitlines()]
native=next(e for e in events if e['type']=='completed' and e.get('scene')==7 and e.get('action')=='turn_right')
assert native['route_source']=='C69292'
req=json.loads((log/'requests'/(native['request_id']+'.json')).read_text())
assert req['result']['route']['geometry_source']=='mapped_connector'
assert math.dist(native['state']['xy'],native['execution']['expected_finish']['xy'])<.4
assert all(m['connector']=='C69292' for m in native['journey']['observed_movements'] if m['action']!='go_straight' and not m.get('road_bend'))
main=[e for e in events if e.get('session_id')==gate['session_id']]
right=next(e for e in main if e['type']=='completed' and e.get('action')=='turn_right')
assert right['state']['speed']>1.5
manifest=json.loads((log/'release-manifest.json').read_text())
for item in manifest['files']:
    for base in [root.parents[1]/'sim',Path('historical-project/apps/driving-demo')]:
        assert hashlib.sha256((base/Path(item['file'])).read_bytes()).hexdigest()==item['sha256']
report=f'''ECE191 v31 investigation and delivery — 2026-10-24

The watched v30 session was 9a17fa03-fa1b-4262-ac56-bf9d8cf8a421. Its final
commands were turn_left then reverse 80 m. The final movement retraced that
left turn backwards at a 1.5 m/s (5.4 km/h) cap, not a forward right turn.

The preceding left turn used J_L63435_L67763. Its incoming lane L63435 has
ordinal 5. Native left turns connect lanes 1, 2, 3 of that road group, not lane
5. Directly reusing them would require extra lateral maneuvers. This update
does not add automatic lane preparation or replace this current-lane path.

Changes: turn selection explicitly tries reachable same-lane mapped connectors
before generated candidates, retaining geometry validation and fallback.
Direction, speed constraint and path provenance are now visible. Inferred
connections are amber and reverse paths purple. Motion speed limits unchanged.

Actual browser acceptance: Scene 1, forward target 20 km/h, reverse cap 5.4 km/h.
Session {gate['session_id']}.
Actual continuous movement {gate['moving_seconds']:.3f} s; wall time through
last command {gate['wall_seconds_to_final_command']:.3f} s; distance {gate['distance_m']:.3f} m.
13/13 commands completed in order: the previous 12-step sequence plus a forward
right turn after reversing. Right-turn completion speed {right['state']['speed']*3.6:.2f} km/h.
Entire journeys checked for requested turn identity, completion position, four
one-lane changes and no unrequested turn. Position jumps {gate['position_jumps']};
layout shifts {gate['layout_shifts']}; console errors 0. Canvas size and document
position stayed fixed. See browser-gate.json and browser-samples.json.

Additional browser checks: Scene 7 right turn used existing C69292 and completed
at the expected position without extra turns. A deliberately unavailable left
lane change timed out, then straight and four alternating one-lane changes
completed in order. The timeout is a recorded failure, not counted as success.

Regression: 19 front-end motion/queue/clock/status tests; 882 map geometry/control
checks with no failures; 9 semantic cases; native-priority/same-lane isolation;
8708 directed adjacency identity checks across overlapping maps. Original human
7x5 comparison remains 25 ready / 10 waiting at starting poses, not 35 successful
browser maneuvers. A separate 13-step virtual integration also passed.

Deployment: {len(manifest['files'])} source/deployed file hashes match. Existing
Windows task supervises http://localhost:8775/. v30 source and original requests
are retained for comparison. These checks cover the stated regression scope;
they do not prove every possible map position/instruction combination.
'''
(out/'delivery-report.txt').write_text(report,encoding='utf-8')
(out/'native-right-audit.json').write_text(json.dumps(dict(passed=True,session_id=native['session_id'],source=native['route_source'],forward_right_finish_speed_kmh=right['state']['speed']*3.6),indent=2))
print(report)
