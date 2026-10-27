"""Check downloaded scene provenance against doPlan GPS, read-only SQLite."""
import bisect, csv, json, sqlite3, sys
from pathlib import Path
root = Path(sys.argv[1]); data = root/'data/nuplan'
clip = '2021.06.09.12.39.51_veh-26_05332_05540'
db = data/f'db/{clip}.db'
with sqlite3.connect(db.as_uri()+'?mode=ro', uri=True) as c:
    assert c.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
    c.row_factory = sqlite3.Row
    log = [dict(r) for r in c.execute('SELECT logfile, location, map_version FROM log')]
    frames = list(c.execute('SELECT timestamp, ego_pose_record_id FROM lidar_pc ORDER BY timestamp'))
    ego_times = {r[0] for r in c.execute('SELECT timestamp FROM ego_pose')}
    counts = {t: c.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
              for t in ['ego_pose','lidar_pc','lidar_box','track','scene']}
with (root/'references/sample_gps.csv').open(newline='',encoding='utf-8-sig') as f:
    gps = list(csv.DictReader(f))
ts = [r['timestamp'] for r in frames]
def nearest(t):
    i = bisect.bisect_left(ts,t)
    return min(abs(t-ts[j]) for j in [i-1,i] if 0<=j<len(ts))
errors = [nearest(int(r['timestamp_us'])) for r in gps]
raw_indices = {t:i for i,t in enumerate(ts)}
affine_matches = sum(raw_indices.get(int(r['timestamp_us'])) == 2*int(r['frame'])+20 for r in gps)
mapping = []
for r in gps:
    i = int(r['frame']); t = int(r['timestamp_us'])
    mapping.append(i<len(ts) and ts[i]==t)
map_path = data/'maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg'
with sqlite3.connect(map_path.as_uri()+'?mode=ro',uri=True) as m:
    map_check = m.execute('PRAGMA quick_check').fetchone()[0]
    layers = m.execute('SELECT table_name,data_type,srs_id FROM gpkg_contents').fetchall()
report = {'log':log,'counts':counts,'gps_rows':len(gps),
    'gps_exact_ego_timestamp_matches':sum(int(r['timestamp_us']) in ego_times for r in gps),
    'gps_exact_lidar_timestamp_matches':sum(e==0 for e in errors),
    'max_nearest_lidar_timestamp_error_us':max(errors),
    'gps_frame_as_zero_based_lidar_index_matches':sum(mapping),
    'observed_sample_mapping': 'raw_lidar_index = 2 * gps.frame + 20 (sample-specific, not a general rule)',
    'observed_mapping_matches': affine_matches,
    'lidar_span_sec':(ts[-1]-ts[0])/1e6,'map_quick_check':map_check,'map_layers':layers,
    'status':'Raw scene verified; video annotation boundaries and MTR adapter still pending'}
(root/'runs/doplan-alignment/nuplan-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
