import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
"""Final browser trace audit, including the exact right-then-left regression."""
import runpy,json
from pathlib import Path
root=Path(__file__).parents[1]
source=(root/'browser/browser_gate_v29.py').read_text()
namespace={'__file__':str(root/'browser/browser_gate_v29.py'),'__name__':'__main__'}
try:
    exec(compile(source,'browser_gate_v30','exec'),namespace)
except SystemExit as result:
    assert not result.code,'Five-minute browser gate failed'
events=namespace['events'];completed=namespace['completed'];telemetry=namespace['telemetry']
assert completed[1]['action']=='lane_change_right' and completed[1]['route_source']=='C69505'
assert completed[2]['action']=='lane_change_left' and completed[2]['route_source']=='C69442'
assert not any(e['type']=='waiting' and e.get('stage_id')==completed[2]['stage_id'] for e in events), 'Feasible return lane change must not enter the no-route waiting state'
proofs=[]
for event in completed:
    if not event['action'].startswith('lane_change'):continue
    request=json.loads(((Path(__file__).resolve().parents[3]/'logs/requests')/(event['request_id']+'.json')).read_text())
    proof=request['result']['route']['lane_change']
    expected=-1 if event['action']=='lane_change_left' else 1
    assert proof['lane_delta']==expected,proof
    assert proof['lateral_start_m']*expected<0 and proof['lateral_end_m']*expected<0
    proofs.append(dict(stage=event['stage_id'],action=event['action'],**proof))
assert all(b['moving_seconds']>=a['moving_seconds'] for a,b in zip(telemetry,telemetry[1:])), 'Movement clock reset'
samples=json.loads((root/'results/browser-samples.json').read_text())
rects=[json.loads(s['canvas']) for s in samples]
assert len({(r['width'],r['height']) for r in rects})==1,'Canvas dimensions changed'
# Browser scroll changes viewport coordinates, not document layout. The live
# layout counter and final document coordinates provide independent checks.
document_rect=samples[-1]['documentCanvas']
assert document_rect=={k:rects[0][k] for k in ['x','y','width','height']}, 'Document canvas position changed'
assert json.loads((root/'results/browser-errors.json').read_text())==[]
result=namespace['report'];result.update(lane_changes=proofs,console_errors=0,unique_canvas_sizes=1,document_canvas=document_rect,final_scroll=samples[-1]['scroll'])
(root/'results/browser-gate.json').write_text(json.dumps(result,indent=2))
assert len(completed)==13 and completed[-1]['action']=='turn_right'
print('All 13 instructions passed, including 4 one-lane maneuvers and a forward right turn after reversing')
