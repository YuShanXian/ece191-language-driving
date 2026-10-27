"""Write fixed timestamp windows and frozen dependencies before any new inference."""
import json,sqlite3
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.turn_windows import choose_windows


def main():
    plan_path=ROOT/'config/turn-challenge-v1.json';plan=json.loads(plan_path.read_text())
    amendment_path=ROOT/'config/turn-challenge-v1-tags.json';amendment=json.loads(amendment_path.read_text())
    if sha256(plan_path)!=amendment['original_plan_sha256']:raise ValueError('Original plan changed')
    downloads_path=ROOT/'runs/project-v2/turn-challenge-v1/downloads.json';downloads=json.loads(downloads_path.read_text())
    if not downloads['complete'] or downloads['specification_sha256']!=sha256(plan_path):raise ValueError('Registered downloads incomplete')
    dependencies=[plan_path,amendment_path,downloads_path,ROOT/'data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg',ROOT/'weights/pretrained_weights/checkpoint_for_val_test.ckpt']
    sources={str(p.relative_to(ROOT)):sha256(p) for p in dependencies};windows=[];records=[]
    frozen_path=ROOT/'runs/project-v2/baseline-v1/frozen-baseline.json';frozen=json.loads(frozen_path.read_text())
    for name,expected in frozen['files'].items():
        if sha256(ROOT/name)!=expected:raise ValueError('Frozen baseline changed: '+name)
        sources[name]=expected
    for index,item in enumerate(plan['selected']):
        path=ROOT/'data/nuplan/db'/(item['clip']+'.db');receipt_path=ROOT/'data/nuplan/receipts'/(item['clip']+'.json');receipt=json.loads(receipt_path.read_text())
        digest=sha256(path)
        if digest!=receipt['sha256']:raise ValueError('Downloaded DB changed')
        sources[str(path.relative_to(ROOT))]=digest;sources[str(receipt_path.relative_to(ROOT))]=sha256(receipt_path)
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as conn:
            metadata=conn.execute('SELECT logfile,location,map_version FROM log').fetchall()
            if metadata!=[(item['clip'],'las_vegas','us-nv-las-vegas-strip')]:raise ValueError('Map/clip mismatch')
            timestamps=[r[0] for r in conn.execute('SELECT timestamp FROM lidar_pc ORDER BY timestamp')]
            tags={name:[r[0] for r in conn.execute('SELECT DISTINCT p.timestamp FROM scenario_tag s JOIN lidar_pc p ON s.lidar_pc_record_id=p.record_id WHERE s.type=? ORDER BY p.timestamp',(name,))] for name in amendment['types']}
        selected,missing=choose_windows(timestamps,tags,plan['fractions'])
        records.append({'clip':item['clip'],'recording_id':item['recording_id'],'log_metadata':metadata,'tag_counts':{k:len(v) for k,v in tags.items()},'selected_count':len(selected),'unavailable':missing})
        for anchor in selected:
            key=f'turn-{index:02d}-t{anchor["timestamp_us"]-timestamps[0]:09d}'
            windows.append({**anchor,'key':key,'clip':item['clip'],'recording_id':item['recording_id'],
                            'sample':'project-v2/turn-challenge-v1/'+key,'run':'project-v2/turn-challenge-v1/'+key})
    implementation={name:sha256(ROOT/name) for name in ['scripts/prepare_turn_challenge.py','scripts/mtr_project/turn_windows.py','scripts/run_turn_challenge.py','scripts/run_project_pipeline.py','scripts/screen_project_scene.py','scripts/mtr_project/sources.py','scripts/mtr_project/planner.py','scripts/mtr_project/stages.py']}
    result={'status':'registered_before_inference','records':records,'windows':windows,'source_sha256':sources,'implementation_sha256':implementation,
            'scope':plan['evaluation_scope'],'annotation_frames_used_for_anchors':False,'official_tag_amendment':amendment}
    output=ROOT/'runs/project-v2/turn-challenge-v1/window-plan.json'
    if output.exists():raise FileExistsError('Window plan already registered')
    write_json(output,result);print(json.dumps({'windows':len(windows),'records':records},indent=2))


if __name__=='__main__':main()
