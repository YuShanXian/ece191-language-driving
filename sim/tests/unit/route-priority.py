"""Native priority must not make a route in another lane reachable."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))
from engine.topology import RoadTopology, Movement
t = RoadTopology.__new__(RoadTopology)
native = Movement('L1', 'C1', 'L2', 'turn_right', -1.57, 2, 1)
inferred = Movement('L1', 'J_L1_L3', 'L3', 'turn_right', -1.57, 0, 0)
adjacent = Movement('L9', 'C9', 'L2', 'turn_right', -1.57, 0, 0)
t.by_lane = {'L1': [inferred, native], 'L9': [adjacent]}
t.by_connector = {}
assert t.options('L1', 'turn_right') == [native, inferred]
t.by_lane['L1'] = [inferred]
assert t.options('L1', 'turn_right') == [inferred]
assert not t.options('L1', 'turn_left')
print('Native-first, no implicit lateral move, and direction filtering passed')
