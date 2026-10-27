"""Read-only diagnostics before language reranking; not a maneuver classifier."""
from pathlib import Path
import csv,json
from collections import Counter
import numpy as np
root=Path(__file__).resolve().parent.parent
out=root/'runs/language-readiness';out.mkdir(exist_ok=True)
report={'warning':'Ego-frame lateral displacement is not lane-relative lane change. No feasibility or instruction success inferred.'}
for name in ['nuplan-first','nuplan-moving']:
    d=np.load(root/f'runs/{name}/prediction_0000.npz')
    c=d['center']; a=c[6]; rot=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
    xy=(d['trajectories']-c[:2]-d['map_center'][:2])@rot
    report[name]=[{'candidate':i+1,'score':float(d['scores'][i]),
        'end_forward_m':float(p[-1,0]),'end_left_m':float(p[-1,1]),
        'max_abs_left_m':float(abs(p[:,1]).max()),
        'mean_last_second_speed_mps':float(np.linalg.norm(np.diff(p[-11:],axis=0),axis=1).mean()*10)}
        for i,p in enumerate(xy)]
with (root/'references/release_annotationsV1.csv').open(encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
report['annotation_reference_counts']=dict(Counter(r['referential_label'] for r in rows if r['passenger_instruction'].strip()))
(out/'audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
