import json,hashlib
import numpy as np
from shapely.geometry import LineString
from types import SimpleNamespace
from navigation_straight import navigation_branches
from select_review_instruction import resolve
from mtr_project.paths import ROOT,write_json

def node(coords):return SimpleNamespace(baseline=LineString(coords))
g=SimpleNamespace(nodes={'a':node([(0,0),(10,0)]),'left':node([(10,0),(20,10)]),'front':node([(10,0),(30,0)])},edges={'a':{'left':'forward','front':'forward'}})
assert navigation_branches(g,['a'],0)['selected']['branch']=='front'
g.edges={'a':{'left':'forward'}}
assert navigation_branches(g,['a'],0)['mode']=='follow_road_fallback'
g.nodes['b']=node([(0,3),(10,3)]);g.edges={'a':{'left':'forward','b':'left'},'b':{'front':'forward'}}
assert navigation_branches(g,['a'],0)['selected']['requires_lane_change']
g.edges={};assert navigation_branches(g,['a'],0)['mode']=='map_unresolved'
assert resolve(3,'\u76f4\u884c')['result']['effective_action']=='follow_road'
assert resolve(7,'\u76f4\u884c')['result']['navigation']['mode']=='forward_road'
assert resolve(3,'\u76f4\u884c')['straight_semantics']=='navigation'
base=ROOT/'runs/project-v3/instruction-priority-v6';data=json.loads((base/'results.json').read_text());old=json.loads((ROOT/'runs/project-v3/instruction-priority-v5/results.json').read_text())
for w,prev in zip(data['windows'],old['windows']):
 assert w['choices'][1:]==prev['choices'][1:]
 for j in range(5):assert (base/f'scene-{w["scene"]:02d}-command-{j}.png').stat().st_size>10000
 if w['scene'] in (3,7):assert all(c['target_retained'] for c in w['choices'][0]['tracking']['cases'])
assert len(json.loads((base/'context-risk.json').read_text())['results'])==35
review=ROOT/'runs/project-v3/language-choice-v1/report-reviewed/human-review/round-2/reviews.json'
assert hashlib.sha256(review.read_bytes()).hexdigest()=='6f1dfa3b17ce65df194354a8946588ae2bf2967f49af2a9476699e328a2b2390'
write_json(base/'verification.json',{'navigation_policy_checks':7,'command_plots':35,'context_annotations':35,'other_actions_unchanged':True,'manual_reviews_unchanged':True,'changed_scene_tracking_retained':'6/6','scope':'Changed navigation examples only; target support is not safety or human success.'})
print('Navigation checks passed; 35 plots; human reviews unchanged; 6/6 tracking cases retained road branch.')
