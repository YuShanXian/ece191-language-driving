"""Post-hoc audit of one CV rejection using recorded future, never selection."""
import json,pickle,sqlite3
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from evaluate_candidate_checks import current_obstacles
from trajectory_checks import footprint
ROOT=Path(__file__).resolve().parent.parent
sample=ROOT/'samples/nuplan-gps700';out=ROOT/'runs/internal-gps700'
conv=json.loads((sample/'conversion.json').read_text());origin=np.asarray(conv['origin_xy_m'])
audit=json.loads((out/'recorded-future-audit.json').read_text())
hit=audit['recorded_path_under_current_CV_collision_check']['first_hits'][0]
obj=next(o for o in current_obstacles(conv)[0] if o['id']==hit['object_id'])
with (sample/conv['scenario']).open('rb') as f:ego=pickle.load(f)['tracks']['ego']['state']
db=next((ROOT/'data/nuplan/db').glob('*.db'));conn=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row
observed=[];cv=[];collisions=[];missing=[]
for step,timestamp in enumerate(conv['timestamp_us'][20:]):
    row=conn.execute('SELECT b.* FROM lidar_box b JOIN lidar_pc pc ON pc.record_id=b.lidar_pc_record_id WHERE pc.timestamp=? AND b.track_record_id=?',
                     (timestamp,bytes.fromhex(obj['id']))).fetchone()
    expected=np.asarray(obj['xy'])+np.asarray(obj['velocity'])*step*.1
    cv.append(expected)
    if row is None:observed.append([float('nan'),float('nan')]);missing.append(step);continue
    xy=np.asarray([row['x'],row['y']])-origin;observed.append(xy)
    idx=step+20
    ego_box=footprint(ego['position'][idx,:2],ego['heading'][idx],ego['length'][idx],ego['width'][idx],.2)
    if ego_box.intersects(footprint(xy,row['yaw'],row['length'],row['width'],.2)):collisions.append(step*.1)
conn.close();observed=np.asarray(observed);cv=np.asarray(cv)
at=int(round(hit['time_sec']/.1))
report={'scope':'Post-hoc check of ONE offending actor at sampled timestamps; not an all-actor safety test.',
        'object_id':obj['id'],'CV_first_hit_sec':hit['time_sec'],'observed_box_overlap_times_sec':collisions,
        'missing_steps':missing,'CV_position_error_at_first_hit_m':float(np.linalg.norm(cv[at]-observed[at])),
        'CV_position_error_at_6_sec_m':float(np.linalg.norm(cv[-1]-observed[-1])),
        'current_velocity_mps':obj['velocity']}
(out/'collision-assumption-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
h=ego['heading'][20];c,s=np.cos(h),np.sin(h);rotation=np.array([[s,c],[-c,s]])
fig,ax=plt.subplots(figsize=(7,7))
for xy,label,color in [(ego['position'][20:,:2],'Recorded ego','#176a49'),(observed,'Recorded other vehicle','#1967bb'),(cv,'Constant-velocity assumption','#e38a24')]:
    p=xy@rotation;ax.plot(p[:,0],p[:,1],label=label,color=color,lw=2);ax.scatter(*p[at],c=color,s=60)
ax.set_aspect('equal');ax.grid(alpha=.3);ax.legend();ax.set_xlabel('Right of initial ego heading (m)');ax.set_ylabel('Forward (m)')
ax.set_title('Why the simple collision check can reject a recorded path\nDots: 1.9 seconds after the current frame')
fig.tight_layout();fig.savefig(out/'collision-assumption-audit.png',dpi=160)
