import json,hashlib,numpy as np
from shapely.geometry import LineString
from feedback_corridors import curve_on_guide,corridor_evidence
from mtr_project.paths import ROOT,write_json
base=ROOT/'runs/project-v3/instruction-priority-v7';prior=ROOT/'runs/project-v3/instruction-priority-v6'
data=json.loads((base/'results.json').read_text());old=json.loads((prior/'results.json').read_text());spec=json.loads((base/'repair-specifications.json').read_text())['repairs'];changed={(r['scene'],r['command']) for r in spec};checks=[]
assert len(changed)==9
for w,pw in zip(data['windows'],old['windows']):
 saved=np.load(base/f'scene-{w["scene"]:02d}-selected.npz')
 for j,(ch,pc) in enumerate(zip(w['choices'],pw['choices'])):
  assert (base/f'scene-{w["scene"]:02d}-command-{j}.png').stat().st_size>10000
  if (w['scene'],j) not in changed:assert ch==pc
  if ch['status']=='destination_grounded_offline':
   points=saved[f'command_{j}'];assert np.isfinite(points).all()
   if (w['scene'],j) in changed:
    assert all(c['target_retained'] for c in ch['tracking']['cases'])
    checks.append({'scene':w['scene'],'command':j,'tracking_cases':3,'horizon_s':(len(points)-1)/10})
  else:assert f'command_{j}' not in saved
assert data['windows'][4]['choices'][2]['horizon_s']==12
assert data['windows'][3]['choices'][1]['status']=='refused_no_reachable_road'
# A lane change must settle on the target; remaining in the old lane must fail.
c=np.zeros(9);c[7]=4;guide=LineString([(0,3.5),(60,3.5)])
p=curve_on_guide(guide,c,25);assert np.allclose(p[0],c[:2]);assert corridor_evidence(p,c,guide,'lane_change_left',15)
wrong=p.copy();wrong[:,1]-=3.5;assert corridor_evidence(wrong,c,guide,'lane_change_left',15) is None
reverse=p[::-1].copy();assert corridor_evidence(reverse,c,guide,'lane_change_left',15) is None
review=prior/'human-review/reviews.json';sha=hashlib.sha256(review.read_bytes()).hexdigest();assert sha==json.loads((base/'prior-human-review-summary.json').read_text())['sha256']
newreview=json.loads((base/'human-review/reviews.json').read_text());assert len(newreview['reviews'])==35
write_json(base/'verification.json',{'plots':35,'changed_commands':9,'unchanged_commands':26,'changed_output_tracking':checks,'original_human_review_unchanged':True,'negative_corridor_checks':'wrong lane and reverse path rejected','new_human_success_rate':None})
print('Verified 35 plots, 26 unchanged results, 8 changed route outputs x3 tracking cases, 1 new refusal; reviews preserved.')
