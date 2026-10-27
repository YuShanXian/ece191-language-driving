"""Read-only audit of doPlan inputs; provisional mapping, never training labels."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys

root = Path(sys.argv[1])
refs = root / 'references'
out = root / 'runs' / 'doplan-alignment'
out.mkdir(parents=True, exist_ok=True)
repo = root / 'vendor' / 'doPlan'
git = ['git', '-c', f'safe.directory={repo.as_posix()}', '-C', str(repo)]
commit = subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip()
source_dir = out / 'upstream-source'
source_dir.mkdir(exist_ok=True)
sources = {}
for name in ['scripts/videoGPSGenerator.py', 'scripts/userLabeler.py', 'build_dashboard.py']:
    data = subprocess.check_output(git + ['show', f'{commit}:{name}'])
    (source_dir / Path(name).name).write_bytes(data)
    sources[name] = {'commit': commit, 'sha256': hashlib.sha256(data).hexdigest()}

def read(name):
    with (refs / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

release = read('release_annotationsV1.csv')
dashboard = read('combined_annotations.csv')
gps = sorted(read('sample_gps.csv'), key=lambda r: int(r['frame']))
assert len({int(r['frame']) for r in gps}) == len(gps), 'Duplicate GPS frame IDs'
times = [int(r['timestamp_us']) for r in gps]
assert all(b > a for a, b in zip(times, times[1:])), 'Non-monotonic GPS times'
clip = '2021.06.09.12.39.51_veh-26_05332_05540'
selected = [r for r in release if r['clip_id'] == clip]
assert selected, 'Sample clip missing from release'
rows = []
for r in selected:
    start, end = int(r['start_frame']), int(r['end_frame'])
    matches = [d for d in dashboard if d['folder'] == clip and
               int(d['start_frame']) == start and int(d['end_frame']) == end and
               d['label'].strip() == r['passenger_instruction'].strip()]
    hypotheses = []
    # Keep both conventions: saved UI position may differ by one from visible image.
    for offset in [0, -1]:
        a, b = start + offset, end + offset
        if 0 <= a < b < len(gps):
            hypotheses.append({'video_index_offset': offset,
                'start_timestamp_us': times[a], 'end_timestamp_us': times[b],
                'start_elapsed_sec': (times[a]-times[0])/1e6,
                'end_elapsed_sec': (times[b]-times[0])/1e6,
                'duration_sec': (times[b]-times[a])/1e6,
                'gps_source_frame_ids': [int(gps[a]['frame']), int(gps[b]['frame'])]})
    rows.append({'annotation': r, 'dashboard_matches': matches,
                 'provisional_video_row_mappings': hypotheses})

report = {'status': 'PROVISIONAL_NOT_FOR_TRAINING_OR_EVALUATION',
    'clip_id': clip, 'expected_db_filename_from_exporter': clip + '.db',
    'sources': sources,
    'input_sha256': {name: hashlib.sha256((refs/name).read_bytes()).hexdigest()
        for name in ['release_annotationsV1.csv', 'combined_annotations.csv', 'sample_gps.csv']},
    'release_rows': len(release), 'dashboard_rows': len(dashboard),
    'gps_rows': len(gps), 'gps_span_sec': (times[-1]-times[0])/1e6,
    'median_gps_interval_sec': statistics.median(b-a for a,b in zip(times,times[1:]))/1e6,
    'annotations': rows,
    'unresolved': ['Verify actual F0 video frame count against 1035 GPS rows and check missing camera frames.',
        'Confirm annotation boundary convention and exporter version used for this clip.',
        'Obtain corresponding nuPlan DB and map; inspect ego, tracked agents, timestamps and map coordinates.',
        'Adapt nuPlan scene to pretrained AV2 model inputs; cross-dataset quality is unvalidated.']}
(out/'alignment.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
lines = ['doPlan \u5355\u7247\u6bb5\u6570\u636e\u5bf9\u9f50\u68c0\u67e5（\u6682\u5b9a，\u4e0d\u53ef\u5f53\u4f5c\u8bad\u7ec3\u6216\u8bc4\u4f30\u6807\u7b7e）', '',
    f'\u7247\u6bb5：{clip}', f'GPS：{len(gps)} \u884c，\u5b9e\u9645\u8de8\u5ea6 {report["gps_span_sec"]:.3f} \u79d2。',
    '\u6e90\u7801\u663e\u793a：\u6807\u6ce8\u4f7f\u7528\u89c6\u9891\u5e27\u4f4d\u7f6e；GPS frame \u4fdd\u5b58\u62bd\u6837\u524d\u8fed\u4ee3\u53f7。',
    'dashboard \u56fa\u5b9a\u6309 10 FPS \u7b97\u65f6\u957f；release \u8868\u7684\u8fd9\u6761\u8bb0\u5f55\u6309 5 FPS \u7b97。',
    '\u89c6\u9891\u5bfc\u51fa\u5668\u5f53\u524d\u6e90\u7801\u8fd8\u5199\u5165 20 FPS，\u56e0\u6b64\u64ad\u653e\u901f\u5ea6\u4e0d\u80fd\u76f4\u63a5\u5f53\u4f5c\u91c7\u96c6\u901f\u5ea6。',
    '\u4e0b\u5217\u65f6\u95f4\u6309\u89c6\u9891\u5e27\u4e0e GPS \u884c\u4e00\u4e00\u5bf9\u5e94\u63a8\u7b97，\u5c1a\u672a\u6838\u5bf9\u5b9e\u9645\u89c6\u9891\u4e0e\u8fb9\u754c\u7ea6\u5b9a。', '']
for row in rows:
    r = row['annotation']
    lines.append(f'{r["annotation_id"]}: {r["passenger_instruction"] or "[\u7a7a\u767d\u6307\u4ee4]"}')
    lines.append(f'\u89c6\u9891\u5e27 {r["start_frame"]}–{r["end_frame"]}；release \u65f6\u957f {r["window_duration_sec"]} \u79d2。')
    for h in row['provisional_video_row_mappings']:
        lines.append(f'  \u504f\u79fb {h["video_index_offset"]}：\u4ece\u9996\u6761 GPS \u8d77 {h["start_elapsed_sec"]:.3f}–{h["end_elapsed_sec"]:.3f} \u79d2。')
lines += ['', '\u4e0b\u4e00\u6b65\u9700\u8981：\u5b9e\u9645 F0.mp4 \u6838\u5bf9\u5e27\u6570；\u5bf9\u5e94 nuPlan .db \u548c\u5730\u56fe\u63d0\u53d6\u8f66\u8f86/\u9053\u8def。',
    '\u8fd9\u91cc\u53ea\u5b8c\u6210\u6570\u636e\u68c0\u67e5，\u5c1a\u672a\u628a doPlan \u63a5\u5165 MTR，\u4e5f\u6ca1\u6709\u8bad\u7ec3\u65b0\u6a21\u578b。',
    'alignment.json \u662f\u7a0b\u5e8f\u8bfb\u53d6\u7684\u68c0\u67e5\u6e05\u5355；upstream-source \u662f\u672c\u6b21\u6838\u5bf9\u7684\u5b98\u65b9\u6e90\u7801\u526f\u672c。']
(out/'\u8bf4\u660e.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print('\n'.join(lines))
