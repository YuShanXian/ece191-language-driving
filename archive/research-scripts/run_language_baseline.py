"""Controlled-instruction counterfactual diagnostics; not labeled benchmark success."""
import argparse,json
from pathlib import Path
import numpy as np
from language_selector import select
root=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser();parser.add_argument('--v2',action='store_true');parser.add_argument('--anchored',action='store_true');args=parser.parse_args()
if args.anchored:args.v2=True
suffix='_anchored' if args.anchored else ('_v2' if args.v2 else '')
instructions=['Keep the lane.','Go straight.','Slow down.','Stop.','Remain stopped.',
              'Merge to the left lane.','Merge to the right lane.','Turn left.','Turn right.',
              'Pull next to the grey van.','Go straight then turn right at the next intersection.']
all_results=[]
for name in ['internal-stopped','internal-moving','internal-lane','internal-gps700','internal-gps900','internal-gps130','internal-gps150']:
    out=root/'runs'/name
    data=json.loads((out/('anchored_feasibility.json' if args.anchored else ('refined_v2_feasibility.json' if args.v2 else 'refined_feasibility.json'))).read_text())
    center=np.load(out/'internal_0000.npz')['center'];speed=float(np.linalg.norm(center[7:9]))
    results=[{'instruction':instruction,**select(instruction,data['candidates'],speed)} for instruction in instructions]
    report={'run':name,'source':'bounded-refined MTR trajectories','refinement_version':2 if args.v2 else 1,'current_speed_mps':speed,
            'instruction_origin':'manually specified diagnostic commands; not verified doPlan labels at this timestamp',
            'results':results}
    report['observed_start_constraint']=args.anchored
    (out/('language_baseline'+suffix+'.json')).write_text(json.dumps(report,indent=2))
    all_results.append(report)
    print(name,[(r['instruction'],r['status'],r['selected_candidate']) for r in results],flush=True)
dest=root/'runs/language-baseline';dest.mkdir(exist_ok=True)
(dest/('results'+suffix+'.json')).write_text(json.dumps(all_results,indent=2))
