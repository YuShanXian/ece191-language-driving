"""Evaluate simple surrounding-actor forecasts on development records only."""
import argparse,json,re,sqlite3
from collections import defaultdict
import numpy as np
from mtr_project.paths import ROOT,write_json,sha256
from mtr_project.sources import source_database
from mtr_project.actor_forecast import fit_observed_motion,forecast,METHODS

def evaluate(record):
    conv=json.loads((ROOT/'samples'/record['sample']/'conversion.json').read_text());now=conv['current_timestamp_us']
    with sqlite3.connect(source_database(conv).as_uri()+'?mode=ro',uri=True) as connection:
        rows=connection.execute('''SELECT b.track_record_id,pc.timestamp,b.x,b.y,b.yaw,b.vx,b.vy,cat.name
        FROM lidar_pc pc JOIN lidar_box b ON b.lidar_pc_record_id=pc.record_id JOIN track tr ON b.track_record_id=tr.record_id
        JOIN category cat ON tr.category_record_id=cat.record_id WHERE pc.timestamp BETWEEN ? AND ? ORDER BY pc.timestamp''',(now-1000000,now+6030000)).fetchall()
    tracks=defaultdict(list)
    for row in rows:tracks[row[0].hex()].append(row[1:])
    results=[];present=0;history_count=0;invalid_history=0
    skipped={str(h):{'missing_future':0,'invalid_future':0} for h in (1.,3.,6.)}
    for identifier,states in tracks.items():
        current=next((row for row in states if row[0]==now),None)
        if current is None or current[-1] not in ('vehicle','pedestrian','bicycle'):continue
        if np.linalg.norm(np.asarray(current[1:3])-conv['origin_xy_m'])>60:continue
        present+=1;history=[row for row in states if row[0]<=now]
        try:model=fit_observed_motion([(r[0]-now)/1e6 for r in history],[r[1:3] for r in history],[r[3] for r in history],current[4:6])
        except ValueError:invalid_history+=1;continue
        history_count+=model['history_available']
        for horizon in (1.,3.,6.):
            target=now+round(horizon*1e6);actual=min(states,key=lambda r:abs(r[0]-target))
            if abs(actual[0]-target)>30000:
                skipped[str(horizon)]['missing_future']+=1;continue
            if not np.all(np.isfinite(actual[1:3])):
                skipped[str(horizon)]['invalid_future']+=1;continue
            errors={method:float(np.linalg.norm(forecast(model,[horizon],method)[0][0]-actual[1:3])) for method in METHODS}
            results.append({'track':identifier,'category':current[-1],'horizon_sec':horizon,'history_available':model['history_available'],'position_error_m':errors})
    return {'scene':record['key'],'recording_id':record['recording_id'],'present_dynamic_actors_within_60m':present,
            'actors_with_history_fit':history_count,'invalid_history_actors':invalid_history,'excluded_by_horizon':skipped,'observations':results}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--name',default='development-comparison-v2');args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.name):raise ValueError('Simple output name required')
    output=ROOT/'runs/project-v2/actor-forecast'/f'{args.name}.json'
    if output.exists():raise ValueError('Preserve prior actor forecast report')
    records=json.loads((ROOT/'runs/project-v2/baseline-v1/development-manifest.json').read_text())
    results=[evaluate(record) for record in records];summary={}
    for horizon in (1.,3.,6.):
        rows=[row for result in results for row in result['observations'] if row['horizon_sec']==horizon]
        excluded={key:sum(r['excluded_by_horizon'][str(horizon)][key] for r in results) for key in ['missing_future','invalid_future']}
        excluded['invalid_history']=sum(r['invalid_history_actors'] for r in results)
        present=sum(r['present_dynamic_actors_within_60m'] for r in results)
        if len(rows)+sum(excluded.values())!=present:raise ValueError('Actor accounting mismatch')
        per_recording={}
        for recording in sorted({r['recording_id'] for r in results}):
            selected=[o for r in results if r['recording_id']==recording for o in r['observations'] if o['horizon_sec']==horizon]
            per_recording[recording]={'count':len(selected),'mean_error_m':{m:float(np.mean([o['position_error_m'][m] for o in selected])) if selected else None for m in METHODS}}
        summary[str(horizon)]={'count':len(rows),'present_actors':present,'excluded':excluded,'per_recording':per_recording,
            'errors_m':{method:{'mean':float(np.mean([r['position_error_m'][method] for r in rows])),
            'median':float(np.median([r['position_error_m'][method] for r in rows])),'p90':float(np.percentile([r['position_error_m'][method] for r in rows],90))} for method in METHODS}}
    report={'summary':summary,'windows':results,'configuration':{'history_seconds':1,'range_m':60,'minimum_history_seconds':.4,'maximum_yaw_rate_abs':1,'future_timestamp_tolerance_ms':30},
            'scope':'Exploratory development-set actor displacement errors, paired across methods. Missing future actors excluded and counted separately. No collision threshold or frozen planner changed. Lower displacement error does not establish safer counterfactual behavior.'}
    report['source_sha256']=sha256(__file__)
    write_json(output,report);print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
