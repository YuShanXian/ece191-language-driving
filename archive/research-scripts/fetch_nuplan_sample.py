"""Fetch selected official ZIP members, CRC checked by zipfile."""
import hashlib, json, sqlite3, sys, zipfile
from pathlib import Path
from inspect_remote_nuplan import Remote, BASE

root = Path(sys.argv[1]); dest = root/'data/nuplan'
clip = '2021.06.09.12.39.51_veh-26_05332_05540'
items = [
    ('nuplan-v1.1_train_vegas_2.zip', f'data/cache/train_vegas_2/{clip}.db', f'db/{clip}.db'),
    ('nuplan-maps-v1.0.zip', 'maps/nuplan-maps-v1.0.json', 'maps/nuplan-maps-v1.0.json'),
    ('nuplan-maps-v1.0.zip', 'maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg', 'maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg'),
    ('nuplan-maps-v1.0.zip', 'LICENSE', 'LICENSE')]
manifest = []
for archive, member, local in items:
    path = dest/local; path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(Remote(archive)) as z:
        info = z.getinfo(member)
        partial = path.with_suffix(path.suffix+'.partial')
        h = hashlib.sha256(); written = 0
        with z.open(info) as src, partial.open('wb') as output:
            while block := src.read(8*1024*1024):
                output.write(block); h.update(block); written += len(block)
                print(f'{local}: {written}/{info.file_size}', flush=True)
        assert written == info.file_size
        partial.replace(path)
        manifest.append({'url': BASE+archive, 'member': member, 'path': str(path),
                         'bytes': written, 'sha256': h.hexdigest(), 'zip_crc_verified': True})
        (dest/'download-manifest.json').write_text(json.dumps(manifest, indent=2))
db = dest/f'db/{clip}.db'
with sqlite3.connect(db.as_uri()+'?mode=ro', uri=True) as conn:
    check = conn.execute('PRAGMA quick_check').fetchall()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    schema = {t: conn.execute(f'PRAGMA table_info("{t}")').fetchall() for t in tables}
    result = {'quick_check': check, 'tables': tables, 'schema': schema}
(dest/'db-inspection.json').write_text(json.dumps(result, indent=2))
print('Completed; database quick_check:', check, flush=True)
