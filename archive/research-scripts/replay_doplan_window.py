"""Replay an actual doPlan annotation window, without assuming command issue time."""
import argparse,json,re,sqlite3
from mtr_project.paths import ROOT,write_json,sha256
from replay_observed_stages import replay

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default='window-v2')
    parser.add_argument('--clip',default='2021.06.09.12.39.51_veh-26_05332_05540')
    parser.add_argument('--annotation-id');parser.add_argument('--conditional-camera-mapping',action='store_true')
    parser.add_argument('--stride',type=int,default=2);args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.tag):raise ValueError('Use a simple output tag')
    clip=args.clip
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+',clip) or '..' in clip:raise ValueError('Invalid clip')
    source=ROOT/'runs/project-v2/video-alignment'/clip/('viewer-alignment.json' if args.conditional_camera_mapping else 'alignment-evidence.json')
    evidence=json.loads(source.read_text());db=ROOT/'data/nuplan/db'/f'{clip}.db'
    digest=sha256(source);snapshot=source.parent/'snapshots'/f'{digest}.json'
    snapshot.parent.mkdir(exist_ok=True)
    if snapshot.exists() and sha256(snapshot)!=digest:raise ValueError('Evidence snapshot hash mismatch')
    if not snapshot.exists():snapshot.write_bytes(source.read_bytes())
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as connection:
        first=connection.execute('SELECT MIN(timestamp) FROM lidar_pc').fetchone()[0]
    for annotation in evidence['annotations']:
        label=annotation['annotation']
        if args.annotation_id and label['annotation_id']!=args.annotation_id:continue
        if not label['instruction'] or not annotation['usable_for_window_level_exploration']:continue
        mapping=annotation['alternatives'][0];out=ROOT/'runs/project-v2/replay'/f'{label["annotation_id"]}-{args.tag}.json'
        if out.exists():raise ValueError('Preserve prior replay')
        report=replay(db,label['instruction'],(mapping['start_timestamp_us']-first)/1e6,mapping['duration_sec'],args.stride)
        report.update(annotation_id=label['annotation_id'],annotation_frame_interval=[label['start_frame'],label['end_frame']],
                      instruction_source='Actual doPlan release annotation; activation at window start is a diagnostic convention, not an observed passenger utterance.',
                      annotation_alignment_sha256=digest,annotation_alignment_snapshot=str(snapshot.relative_to(ROOT)),
                      replay_source_sha256=sha256(ROOT/'scripts/replay_observed_stages.py'),
                      command_issue_time_known=False)
        report['alignment_basis']=annotation.get('mapping_basis',evidence.get('source_contract'))
        report['alignment_status']=annotation['status']
        write_json(out,report);print(json.dumps({k:v for k,v in report.items() if k!='trace'},indent=2))

if __name__=='__main__':main()
