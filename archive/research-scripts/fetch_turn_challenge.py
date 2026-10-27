"""Download only preregistered ZIP members; preserve validated cached files."""
import hashlib,json,shutil,sqlite3,zipfile
from pathlib import PurePosixPath
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.remote_zip import VerifiedRemoteZip

BASE='https://motional-nuplan.s3.ap-northeast-1.amazonaws.com/public/nuplan-v1.1/'


def fetch(item):
    target=ROOT/'data/nuplan/db'/(item['clip']+'.db');receipt=ROOT/'data/nuplan/receipts'/(item['clip']+'.json')
    if target.exists():
        saved=json.loads(receipt.read_text())
        if target.stat().st_size!=item['bytes'] or sha256(target)!=saved['sha256'] or saved['member']!=item['member'] or saved['source']!=BASE+item['archive']:raise ValueError('Existing DB identity mismatch')
        return saved
    if PurePosixPath(item['member']).name!=item['clip']+'.db' or '/' in item['archive']:raise ValueError('Unexpected archive identity')
    if shutil.disk_usage(ROOT).free<item['bytes']+2*1024**3:raise OSError('Insufficient free disk')
    partial=target.with_suffix('.db.partial');digest=hashlib.sha256();written=0
    remote=VerifiedRemoteZip(BASE+item['archive'],budget=item['compressed_bytes']+16*1024**2)
    with zipfile.ZipFile(remote) as archive:
        member=archive.getinfo(item['member'])
        if (member.file_size,member.compress_size,member.CRC)!=(item['bytes'],item['compressed_bytes'],item['crc32']):raise ValueError('Catalog and remote ZIP differ')
        with archive.open(member) as stream,partial.open('wb') as output:
            while block:=stream.read(4*1024**2):
                written+=len(block)
                if written>item['bytes']:raise ValueError('Member exceeds registered length')
                output.write(block);digest.update(block)
    if written!=item['bytes']:raise ValueError('Incomplete member')
    with sqlite3.connect(partial.as_uri()+'?mode=ro',uri=True) as conn:
        if conn.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('Invalid SQLite database')
        if conn.execute('SELECT logfile FROM log').fetchall()!=[(item['clip'],)]:raise ValueError('Wrong driving log')
    partial.replace(target)
    result={'clip':item['clip'],'bytes':written,'sha256':digest.hexdigest(),'source':remote.url,'member':item['member'],
            'archive_etag':remote.etag,'network_bytes':remote.used,'zip_crc_verified':True,'sqlite_quick_check':'ok'}
    write_json(receipt,result);print(json.dumps(result),flush=True);return result


def main():
    path=ROOT/'config/turn-challenge-v1.json';plan=json.loads(path.read_text())
    for name,expected in plan['source_sha256'].items():
        if sha256(ROOT/name)!=expected:raise ValueError('Registered catalog changed')
    receipts=[];output=ROOT/'runs/project-v2/turn-challenge-v1/downloads.json'
    for item in plan['selected']:
        receipts.append(fetch(item));write_json(output,{'specification_sha256':sha256(path),'downloads':receipts,'complete':len(receipts)==len(plan['selected'])})


if __name__=='__main__':main()
