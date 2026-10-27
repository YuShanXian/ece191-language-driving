"""Continue bounded positive-name search after an initial camera search misses."""
import concurrent.futures
import json
from locate_raw_camera_samples import Archive, MIB
from mtr_project.paths import ROOT, write_json


def main():
    folder=ROOT/'runs/project-v2/alignment-review-v1'
    path=folder/'camera-6-location-probes.json'; location=json.loads(path.read_text())
    previous=json.loads((folder/'camera-6-fetch-discovery.json').read_text())
    # Continue after the last observed CAM_R2 sample in the target clip.
    start=max(p['start'] for p in previous['probes'])
    archive=Archive(location['archive'],budget=16*MIB)
    clip=next(iter(location['archive']['target_positions']))
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        probes=list(pool.map(archive.probe,[start+i*128*MIB for i in range(1,13)]))
    hits=[h for p in probes for h in p['headers'] if '/'+clip+'/CAM_F0/' in h['name']]
    location['additional_target_camera_probes']=probes
    location['additional_probe_strategy']='Twelve 128MiB-spaced probes after last observed target CAM_R2; exact-name positive matches only.'
    known={h['offset'] for h in location['found']}
    location['found'].extend(h for h in hits if h['offset'] not in known)
    location['additional_network_bytes_this_run']=archive.used
    write_json(path,location)
    print(json.dumps({'hits':hits,'network_bytes':archive.used},indent=2))


if __name__=='__main__':main()
