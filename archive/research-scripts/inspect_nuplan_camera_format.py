"""Inspect official inventory and first archive bytes before selecting a bounded extraction method."""
import json,urllib.request
from mtr_project.paths import ROOT,sha256,write_json
from inspect_remote_nuplan import Remote,BASE


def main():
    folder=ROOT/'runs/project-v2/alignment-review-v1';index=json.loads((folder/'official-train-index.json').read_text())
    inventory=next(x for x in index['objects'] if x['key'].endswith('/public_set_train_sensor.txt'))
    url='https://motional-nuplan.s3.ap-northeast-1.amazonaws.com/'+inventory['key']
    with urllib.request.urlopen(url,timeout=30) as response:body=response.read(65537)
    if len(body)>65536 or len(body)!=inventory['size']:raise ValueError('Inventory size mismatch or bound exceeded')
    path=folder/'official-train-sensor.txt';path.write_bytes(body);lines=body.decode().splitlines()
    first=next(x for x in index['objects'] if x['key'].endswith('/nuplan-v1.1_train_camera_0.zip'))
    remote=Remote(first['key'].removeprefix('public/nuplan-v1.1/'))
    head=remote.read(1024);remote.seek(-65536,2);tail=remote.read(65536)
    (folder/'camera-0-header.bin').write_bytes(head);(folder/'camera-0-tail.bin').write_bytes(tail)
    result={'inventory_url':url,'inventory_sha256':sha256(path),'inventory_lines':len(lines),'first_inventory_lines':lines[:8],
        'requested_clips_present':{clip:sum(clip in line for line in lines) for clip in ['2021.06.09.12.39.51_veh-26_05332_05540','2021.06.09.18.23.43_veh-35_00026_00274']},
        'archive_url':remote.url,'archive_bytes':remote.size,'observed_index_size':first['size'],'header_hex':head[:32].hex(),
        'tar_magic_at_257':head[257:265].decode('ascii',errors='replace'),'zip_eocd_offset_within_tail':tail.rfind(b'PK\x05\x06'),
        'network_bytes_read':len(body)+len(head)+len(tail)}
    write_json(folder/'official-camera-format.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
