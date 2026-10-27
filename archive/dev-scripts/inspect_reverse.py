import json
from fixtures import ROOT, load_scene
s=load_scene(1)
print('BEND', s.topology.by_connector['C64857'])
for m in s.topology.by_connector.values():
    if s.nodes[m.target].lane_group == s.nodes[s.topology.by_connector['C64857'].target].lane_group:
        print('BEND INCOMING',m)
for number in [5,12]:
    data=json.loads((ROOT.parent/'refactor-v36/results/human-review-reverse'/f'instruction-{number}-request.json').read_text())
    state=data['request']['state']; key,offset=s.locate(state)
    print('REQUEST',number,key,offset, s.nodes[key].baseline.length)
    if key in s.topology.by_connector:
        print('CONNECTOR',s.topology.by_connector[key]); key=s.topology.by_connector[key].source
    for depth in range(5):
        incoming=[m for ms in s.topology.by_lane.values() for m in ms if m.target==key]
        print(key,[(m.source,m.connector,m.action,m.road_bend,m.rank_error,round(m.lateral,2),m.connector in s.topology.forward.get(m.source,[])) for m in incoming])
        neutral=[m for m in incoming if s.topology.is_neutral(m) and m.rank_error==0]
        if not neutral:break
        key=min(neutral,key=lambda m:(abs(m.lateral),m.connector.startswith('J_'))).source
