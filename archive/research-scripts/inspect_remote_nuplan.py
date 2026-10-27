"""Inspect official ZIPs via bounded HTTP ranges; no full archive download."""
import io, json, sys, urllib.request, zipfile
from pathlib import Path

BASE = 'https://motional-nuplan.s3.ap-northeast-1.amazonaws.com/public/nuplan-v1.1/'
class Remote(io.RawIOBase):
    def __init__(self, name):
        self.url = BASE + name
        with urllib.request.urlopen(urllib.request.Request(self.url, method='HEAD'), timeout=60) as r:
            self.size = int(r.headers['Content-Length'])
        self.pos = 0
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos
    def read(self, n=-1):
        n = min(self.size-self.pos, n if n >= 0 else self.size-self.pos)
        if not n: return b''
        if n > 64*1024*1024: raise ValueError('Range exceeds 64 MiB safety bound')
        req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{self.pos+n-1}'})
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.status != 206: raise RuntimeError('Server ignored range; refusing full download')
            data = r.read(n)
        if len(data) != n: raise IOError('Short range')
        self.pos += n
        return data

if __name__ == '__main__':
    root = Path(sys.argv[1]); target = '2021.06.09.12.39.51_veh-26_05332_05540.db'
    results = []
    for name in ['nuplan-v1.1_mini.zip'] + [f'nuplan-v1.1_train_vegas_{i}.zip' for i in range(1,7)]:
        with zipfile.ZipFile(Remote(name)) as z:
            matches = [{'name': i.filename, 'size': i.file_size, 'compressed_size': i.compress_size}
                       for i in z.infolist() if i.filename.endswith(target)]
            print(name, 'entries', len(z.infolist()), 'matches', matches, flush=True)
            results.append({'archive': name, 'entries': len(z.infolist()), 'matches': matches})
            if matches: break
    (root/'runs/doplan-alignment/remote-archive-search.json').write_text(json.dumps(results,indent=2))
