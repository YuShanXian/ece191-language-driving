"""Recover the exact earlier evidence bytes referenced by the first replay.

The only later change to that evidence was adding ego_xy_m to each frame.
Accept reconstruction only if its SHA-256 equals the replay's recorded hash.
"""
import hashlib,json
from mtr_project.paths import ROOT,write_json

clip='2021.06.09.12.39.51_veh-26_05332_05540'
folder=ROOT/'runs/project-v2/video-alignment'/clip
legacy=ROOT/'runs/project-v2/replay/doplan_006160-window.json'
expected=json.loads(legacy.read_text())['annotation_alignment_sha256']
value=json.loads((folder/'alignment-evidence.json').read_text())
for frame in value['frame_mapping']:frame.pop('ego_xy_m',None)
raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
actual=hashlib.sha256(raw).hexdigest()
if actual!=expected:raise ValueError(f'Cannot reconstruct exact legacy evidence: {actual} != {expected}')
target=folder/'snapshots'/f'{expected}.json';target.parent.mkdir(exist_ok=True)
if target.exists() and target.read_bytes()!=raw:raise ValueError('Existing snapshot differs')
if not target.exists():target.write_bytes(raw)
write_json(folder/'legacy-snapshot-recovery.json',{'legacy_replay':str(legacy.relative_to(ROOT)),
    'snapshot':str(target.relative_to(ROOT)),'sha256':actual,
    'method':'Remove subsequently added ego_xy_m fields; exact match against pre-existing replay hash required.'})
print('Recovered exact legacy evidence:',target)
