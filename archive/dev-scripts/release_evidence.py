import json,hashlib
from pathlib import Path
root=Path(__file__).parents[1];out=root/'results'
target=Path('historical-project/apps/driving-demo');files=[]
for f in (root.parents[1]/'sim').rglob('*'):
 if not f.is_file() or '__pycache__' in f.parts:continue
 rel=f.relative_to(root.parents[1]/'sim');live=target/rel
 digest=hashlib.sha256(f.read_bytes()).hexdigest()
 assert hashlib.sha256(live.read_bytes()).hexdigest()==digest,str(rel)
 files.append(dict(file=str(rel),sha256=digest))
gate=json.loads((out/'browser-gate.json').read_text())
assert gate['passed'] and gate['moving_seconds']>=300
assert gate['commands']['bend'][-1]['source']=='C64857'
cfg=json.loads((out/'browser-run-config.json').read_text())
assert cfg['timeout']['expected']==[['lane_change_left','timed_out'],['go_straight','completed']]
report=dict(release='refactor-v35',installed_files_verified=files,
 changes=['Straight prefers a real straight exit, otherwise follows the natural forward road bend; U-turns remain explicit.',
 'English interface; queue follows the current instruction without scrolling the page.',
 'Leftmost lane and Rightmost lane buttons, including already-selected behavior.',
 'Explicit stop context for map boundaries and requested stopping distances.'],
 browser=gate,physical_destinations=json.loads((out/'browser-physical-destinations.json').read_text()),
 regressions=json.loads((out/'v35-regression.json').read_text()),
 random_exploration=json.loads((out/'random-coverage.json').read_text()),
 limitations=['Random exploration retains 80 unresolved instructions across 43 of 70 sessions; this release does not claim universal command success.',
 'The separately retained main-extreme-unresolved.json changes the northbound road to its far-right lane; its later left-turn request timed out. No feasibility conclusion is asserted.'],
 source_archive='../refactor-v34/app',
 original_user_evidence='user-session.json, user-requests, user-stop-fixture.json, original-user-stop-spec.json.replayed.json')
(out/'delivery-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(dict(release=report['release'],files=len(files),browser_seconds=gate['moving_seconds'],
 main_commands=len(gate['commands']['main']),bend_commands=len(gate['commands']['bend']),
 timeout_verified=True,source_hashes_verified=True)))
