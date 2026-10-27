"""Read bounded official archive samples; never download a whole camera archive."""
import json
import re
import tarfile
import urllib.request
from mtr_project.paths import ROOT, write_json


def headers(body, start):
    found = []
    for offset in range((-start) % 512, len(body) - 511, 512):
        block = body[offset:offset + 512]
        if block[257:262] != b'ustar':
            continue
        try:
            entry = tarfile.TarInfo.frombuf(block, 'utf-8', 'strict')
        except (tarfile.TarError, UnicodeError, ValueError):
            continue
        found.append({'offset': start + offset, 'name': entry.name, 'size': entry.size,
                      'type': entry.type.decode('ascii', errors='replace')})
    return found


def main():
    folder = ROOT / 'runs/project-v2/alignment-review-v1'
    index = json.loads((folder / 'official-train-index.json').read_text())
    packet = json.loads((folder / 'review-packet.json').read_text())
    targets = {x['clip'] for x in packet['requests']}
    groups = {}
    for line in (folder / 'official-train-sensor.txt').read_text().splitlines():
        if line.startswith('File group:'):
            group = int(line.split(':')[1]); groups[group] = []
        elif line.strip():
            groups[group].append(line.strip())
    result = []
    for group, clips in groups.items():
        selected = [x for x in clips if x in targets]
        if not selected:
            continue
        obj = next(x for x in index['objects'] if x['key'].endswith(f'/nuplan-v1.1_train_camera_{group}.zip'))
        url = 'https://motional-nuplan.s3.ap-northeast-1.amazonaws.com/' + obj['key']
        n = 1048576
        request = urllib.request.Request(url, headers={'Range': f'bytes=0-{n-1}'})
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 206 or response.headers.get('Content-Range') != f'bytes 0-{n-1}/{obj["size"]}':
                raise ValueError('Server did not honor exact bounded range')
            etag = response.headers.get('ETag')
            body = response.read(n + 1)
        if len(body) != n:
            raise ValueError('Unexpected response size')
        (folder / f'camera-{group}-first-mib.bin').write_bytes(body)
        result.append({'group': group, 'url': url, 'size': obj['size'], 'etag': etag,
                       'group_clip_count': len(clips), 'target_positions': {x: clips.index(x) for x in selected},
                       'group_clips': clips, 'headers': headers(body, 0), 'network_bytes': len(body)})
    write_json(folder / 'target-camera-archives.json', result)
    for item in result:
        print(json.dumps({k: v for k, v in item.items() if k != 'group_clips'}, indent=2))


if __name__ == '__main__':
    main()
