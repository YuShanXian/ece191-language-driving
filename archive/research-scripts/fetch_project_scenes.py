"""Download only preregistered official DB members, with CRC/hash/SQLite validation."""
import concurrent.futures
import json
import shutil
import sqlite3
import zipfile
import hashlib
from mtr_project.paths import ROOT, write_json
from inspect_remote_nuplan import Remote, BASE

def fetch(item):
    path=ROOT/'data/nuplan/db'/f"{item['clip']}.db"
    receipt=ROOT/'data/nuplan/receipts'/f"{item['clip']}.json"
    if path.exists():
        if not receipt.exists():raise FileExistsError(f'Unverified preexisting DB: {path}')
        record=json.loads(receipt.read_text())
        if path.stat().st_size!=record['bytes']:raise ValueError('Cached file size changed')
        return record
    if shutil.disk_usage(ROOT).free < item['bytes']+2*1024**3:raise OSError('Insufficient free disk')
    path.parent.mkdir(parents=True,exist_ok=True)
    partial=path.with_suffix('.db.partial')
    digest=hashlib.sha256();written=0
    with zipfile.ZipFile(Remote(item['archive'])) as archive:
        info=archive.getinfo(item['member'])
        if info.file_size!=item['bytes'] or info.CRC!=item['crc32']:raise ValueError('Remote archive changed since registration')
        with archive.open(info) as stream,partial.open('wb') as output:
            while block:=stream.read(4*1024*1024):
                output.write(block);digest.update(block);written+=len(block)
    if written!=item['bytes']:raise ValueError('Incomplete download')
    with sqlite3.connect(partial.as_uri()+'?mode=ro',uri=True) as conn:
        if conn.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('SQLite quick_check failed')
        clip=conn.execute('SELECT logfile FROM log LIMIT 1').fetchone()[0]
        if clip!=item['clip']:raise ValueError('Wrong driving log')
    partial.replace(path)
    record={'clip':item['clip'],'bytes':written,'sha256':digest.hexdigest(),'source':BASE+item['archive'],
            'member':item['member'],'zip_crc_verified':True,'sqlite_quick_check':'ok'}
    write_json(receipt,record)
    print('Downloaded and verified:',item['clip'],written,flush=True)
    return record

if __name__=='__main__':
    config=json.loads((ROOT/'config/project-v2-scenes.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(fetch,config['selected']))
    write_json(ROOT/'runs/project-v2/catalog/downloads.json',results)
