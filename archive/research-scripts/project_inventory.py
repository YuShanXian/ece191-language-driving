"""Read existing labels and data; publish a reproducible inventory, no inference."""
import json
import sqlite3
from pathlib import Path
from collections import Counter
from mtr_project.paths import ROOT, write_json
from mtr_project.annotations import load_release, inventory, align_to_gps
from language_selector import parse_instruction

def main():
    records, source = load_release(ROOT/'references/release_annotationsV1.csv')
    report = inventory(records, parse_instruction)
    report['source'] = source
    report['recording_count'] = len({r.recording_id for r in records})
    local = []
    for db in sorted((ROOT/'data/nuplan/db').glob('*.db')):
        with sqlite3.connect(db.as_uri()+'?mode=ro', uri=True) as conn:
            stamps = [row[0] for row in conn.execute('SELECT timestamp FROM lidar_pc ORDER BY timestamp')]
            metadata = dict(zip([x[1] for x in conn.execute('PRAGMA table_info(log)')], conn.execute('SELECT * FROM log LIMIT 1').fetchone()))
            metadata = {k: v.hex() if isinstance(v, bytes) else v for k,v in metadata.items()}
        local.append({'clip': db.stem, 'bytes': db.stat().st_size, 'frames': len(stamps),
                      'duration_sec': (stamps[-1]-stamps[0])/1e6, 'metadata': metadata})
        if db.stem == '2021.06.09.12.39.51_veh-26_05332_05540':
            aligned = [align_to_gps(r, ROOT/'references/sample_gps.csv', stamps)
                       for r in records if r.clip_id == db.stem]
            write_json(ROOT/'runs/project-v2/inventory/alignment.json', aligned)
    report['local_databases'] = local
    write_json(ROOT/'runs/project-v2/inventory/annotations.json', report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('clips', 'unsupported_examples')}, indent=2))
    print('Examples:', json.dumps(report['unsupported_examples'], indent=2))

if __name__ == '__main__':
    main()
