# Following an instruction means executing its actions in order

The input is a natural-language navigation instruction, a current vehicle pose
and speed, and a road map. nuPlan supplies maps and recorded scene state/history;
doPlan supplies language annotations associated with driving windows.
The desired output is a connected trajectory whose execution respects the
instruction's action order, distances, and stopping conditions.

“Turn right” requires finding a reachable right-turn opportunity. It may require
changing lanes first. “Then stop” must wait for the preceding maneuver to finish.
A new instruction during playback must use the current pose, and a late planning
reply must not overwrite an already cancelled or replaced command.

Trajectory prediction and instruction following therefore address different
questions. A predicted future can fit the recorded drive yet fail a different
requested route. A geometrically plausible curve can also fail to execute the
requested maneuver. We need explicit action state, map connectivity, and evidence
of completion as well as a route.

Doh explores selecting pretrained MTR candidates using language. Yushan explores
constructing routes from map topology and playing them through an instruction
queue. These are parallel tracks. Yushan's earlier MTR experiments were abandoned
for her track and are archived; this is not a team-wide abandonment of MTR.

The current demonstration excludes obstacle interaction, traffic-light timing,
legal driving decisions, vehicle dynamics, and deployment to a real vehicle.
