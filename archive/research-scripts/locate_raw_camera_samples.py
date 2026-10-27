"""Bounded, resumable TAR range probing of publicly indexed nuPlan camera archives.

Archive order is not assumed sorted. Positive hits are exact checksummed TAR names;
failure to find a name is not proof of absence. No full archive downloads allowed.
"""
import argparse
import concurrent.futures
import hashlib
import json
import threading
import urllib.request
from pathlib import Path
from probe_target_camera_archives import headers
from mtr_project.paths import ROOT, write_json

MIB = 1024 * 1024


class Archive:
    def __init__(self, item, budget=128*MIB):
        self.item = item
        self.root = ROOT / 'runs/project-v2/alignment-review-v1/archive-ranges' / str(item['group'])
        self.root.mkdir(parents=True, exist_ok=True)
        self.budget = budget
        self.used = 0
        self.lock = threading.Lock()

    def read(self, start, size):
        if start < 0 or size <= 0 or size > 2*MIB or start+size > self.item['size']:
            raise ValueError('Range outside permitted bounds')
        path = self.root / f'{start}-{size}.bin'
        receipt = path.with_suffix('.json')
        if path.exists() and receipt.exists():
            body = path.read_bytes()
            meta = json.loads(receipt.read_text())
            if (len(body) != size or meta['sha256'] != hashlib.sha256(body).hexdigest()
                or meta['etag'] != self.item['etag'] or meta['url'] != self.item['url']):
                raise ValueError('Cached range identity/hash mismatch')
            return body
        with self.lock:
            if self.used + size > self.budget:
                raise ValueError('Per-run network budget exhausted')
            self.used += size
        request = urllib.request.Request(self.item['url'], headers={
            'Range': f'bytes={start}-{start+size-1}', 'If-Match': self.item['etag']})
        with urllib.request.urlopen(request, timeout=30) as response:
            if (response.status != 206 or response.headers.get('ETag') != self.item['etag']
                or response.headers.get('Content-Range') != f'bytes {start}-{start+size-1}/{self.item["size"]}'):
                raise ValueError('Remote object changed or range not honored')
            body = response.read(size+1)
        if len(body) != size:
            raise ValueError('Range length mismatch')
        partial = path.with_suffix('.partial'); partial.write_bytes(body); partial.replace(path)
        write_json(receipt, {'url': self.item['url'], 'etag': self.item['etag'], 'start': start,
                            'size': size, 'sha256': hashlib.sha256(body).hexdigest()})
        return body

    def probe(self, start, size=MIB//2):
        start = (start//512)*512
        size = min(size, self.item['size']-start)
        found = headers(self.read(start, size), start)
        if not found and size < 2*MIB:
            found = headers(self.read(start, min(2*MIB, self.item['size']-start)), start)
        return {'start': start, 'headers': found}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--group', type=int, required=True)
    args = parser.parse_args()
    folder = ROOT/'runs/project-v2/alignment-review-v1'
    item = next(x for x in json.loads((folder/'target-camera-archives.json').read_text()) if x['group']==args.group)
    archive = Archive(item)
    targets = list(item['target_positions'])
    out = folder/f'camera-{args.group}-location-probes.json'
    result = {'archive': item, 'strategy': 'Uniform 1GiB probes, stopping on exact clip-name hit. No assumed sorting or absence claim.',
              'samples': [], 'found': [], 'network_bytes_this_run': 0}
    # An archive contains contiguous camera folders, but no ordering assumption is
    # used to skip unobserved names. Each positive match comes from a TAR checksum.
    starts = range(0, item['size'], 1024*MIB)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for offset in range(0, len(starts), 6):
            batch = list(pool.map(archive.probe, starts[offset:offset+6]))
            result['samples'].extend(batch)
            result['found'] = [h for s in result['samples'] for h in s['headers']
                               if any('/'+clip+'/' in h['name'] for clip in targets)]
            result['network_bytes_this_run'] = archive.used
            write_json(out, result)
            print(json.dumps({'group': args.group, 'probes': len(result['samples']), 'bytes': archive.used,
                              'hits': len(result['found'])}), flush=True)
            if result['found']:
                break
    print(json.dumps({'result': str(out), 'found': result['found']}, indent=2), flush=True)


if __name__ == '__main__':
    main()
