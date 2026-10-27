"""Retrieve only requested exact-name JPEGs via validated HTTP ranges in a TAR."""
import argparse
import concurrent.futures
import io
import json
from pathlib import PurePosixPath
from PIL import Image
from locate_raw_camera_samples import Archive, MIB
from probe_target_camera_archives import headers
from mtr_project.paths import ROOT, sha256, write_json


def walk(archive, start, stop, wanted):
    matches = []
    count = 0
    offset = start
    while offset < stop:
        found = headers(archive.read(offset, 512), offset)
        if len(found) != 1 or found[0]['offset'] != offset:
            raise ValueError(f'Invalid TAR header at {offset}')
        entry = found[0]
        count += 1
        if count > 2048:
            raise ValueError('Shard header-count bound exceeded')
        if entry['name'] in wanted:
            if entry['type'] != '0' or not 0 < entry['size'] <= 2*MIB:
                raise ValueError('Requested image is not a bounded regular file')
            body = archive.read(offset + 512, entry['size'])
            with Image.open(io.BytesIO(body)) as image:
                if image.format != 'JPEG':
                    raise ValueError('Requested file is not JPEG')
                dimensions = list(image.size)
                image.verify()
            relative = wanted[entry['name']]
            path = ROOT / 'data/nuplan/sensor_blobs' / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.read_bytes() != body:
                raise ValueError('Refuse replacing different original image')
            if not path.exists():
                partial = path.with_suffix('.partial'); partial.write_bytes(body); partial.replace(path)
            matches.append({**entry, 'raw_filename_from_database': relative,
                            'file': str(path.relative_to(ROOT)), 'sha256': sha256(path),
                            'dimensions': dimensions, 'archive_url': archive.item['url'],
                            'archive_etag': archive.item['etag']})
        offset += 512 + ((entry['size'] + 511)//512)*512
        if entry['size'] < 0 or offset > archive.item['size']:
            raise ValueError('Invalid TAR member size')
    return {'start': start, 'stop': stop, 'next_header': offset, 'headers_checked': count, 'matches': matches}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--group', required=True, type=int)
    args = parser.parse_args()
    folder = ROOT/'runs/project-v2/alignment-review-v1'
    packet_path = folder/'review-packet.json'
    packet = json.loads(packet_path.read_text())
    location = json.loads((folder/f'camera-{args.group}-location-probes.json').read_text())
    item = location['archive']; archive = Archive(item, budget=96*MIB)
    clip = next(iter(item['target_positions']))
    wanted = {}
    prefix = f'nuplan-v1.1_train_camera_{args.group}/'
    for request in packet['requests']:
        if request['clip'] != clip:
            continue
        relative = request['raw_filename_from_database']; parts = PurePosixPath(relative)
        if parts.is_absolute() or '..' in parts.parts or '\\' in relative or parts.parts[:2] != (clip, 'CAM_F0'):
            raise ValueError('Unexpected requested path')
        wanted[prefix + relative] = relative
    camera_prefix = prefix+clip+'/CAM_F0/'
    seeds = [h for h in location['found'] if h['name'].startswith(camera_prefix)]
    probes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        if not seeds:
            center = location['found'][0]['offset']
            starts = [max(0, center + d*128*MIB) for d in range(-16, 17)]
            probes = list(pool.map(archive.probe, sorted(set(starts))))
            seeds = [h for sample in probes for h in sample['headers'] if h['name'].startswith(camera_prefix)]
        if not seeds:
            write_json(folder/f'camera-{args.group}-fetch-discovery.json', {'probes':probes,'status':'no_CAM_F0_in_bounded_probes'})
            raise ValueError('CAM_F0 not located within bounded probe plan; no absence claim')
        seed = seeds[0]['offset']; bounds = []
        # Find nearby samples outside this camera folder. This narrows a positive
        # search; completeness is established only by finding all requested names.
        for direction in [-1, 1]:
            for step in range(1, 33):
                sample = archive.probe(seed + direction*step*32*MIB); probes.append(sample)
                if sample['headers'] and not any(h['name'].startswith(camera_prefix) for h in sample['headers']):
                    bounds.append(sample['headers'][0]['offset']); break
            else:
                raise ValueError('Could not bracket camera folder within 1GiB')
        lower, upper = sorted(bounds)
        shard_probes = list(pool.map(archive.probe, range(lower, upper, 16*MIB)))
        probes.extend(shard_probes)
        if any(not sample['headers'] for sample in shard_probes):
            raise ValueError('No TAR header for a shard boundary')
        starts = sorted(set([lower, upper] + [p['headers'][0]['offset'] for p in shard_probes]))
        write_json(folder/f'camera-{args.group}-fetch-discovery.json', {'probes':probes,'bounds':bounds,'shard_starts':starts})
        print(json.dumps({'group':args.group,'search_span_bytes':upper-lower,'shards':len(starts)-1,'network_bytes':archive.used}),flush=True)
        futures = [pool.submit(walk, archive, start, stop, wanted) for start, stop in zip(starts, starts[1:])]
        shards = []
        receipt = {'group':args.group,'clip':clip,'packet_sha256':sha256(packet_path),
                   'script_sha256':sha256(__file__),'archive':item,'shards':shards,'complete':False}
        output = folder/f'camera-{args.group}-download-receipt.json'
        for future in concurrent.futures.as_completed(futures):
            shards.append(future.result())
            receipt['network_bytes_this_run'] = archive.used
            write_json(output, receipt)
            print(json.dumps({'group':args.group,'completed_shards':len(shards),'matches':sum(len(s['matches']) for s in shards)}),flush=True)
        matches = [m for shard in shards for m in shard['matches']]
        if len(matches)!=len(wanted) or {m['name'] for m in matches}!=set(wanted):
            raise ValueError('Not every requested exact filename found; preserve partial receipt')
        receipt['complete']=True; receipt['requested_images']=len(wanted)
        receipt['network_bytes_this_run']=archive.used; write_json(output,receipt)
        print(json.dumps({'complete':True,'receipt':str(output),'images':len(matches),'network_bytes':archive.used}),flush=True)


if __name__ == '__main__':
    main()
