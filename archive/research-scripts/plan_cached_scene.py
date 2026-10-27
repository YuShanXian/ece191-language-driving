"""One-command offline language selection on existing MTR results."""
import argparse,json
from mtr_project.paths import ROOT,write_json
from mtr_project.planner import OfflinePlanner
from mtr_project.stages import Observation

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',default='internal-moving',help='Path under runs/')
    p.add_argument('--instruction',required=True)
    p.add_argument('--output',help='Optional JSON under runs/project-v2/interactive/')
    args=p.parse_args()
    report=json.loads((ROOT/'runs'/args.run/'anchored_feasibility.json').read_text())
    sample=ROOT/'samples'/report['summary']['sample']
    conversion=json.loads((sample/'conversion.json').read_text())
    # Current-only observation: spatial/temporal triggers correctly remain waiting.
    observation=Observation(conversion['current_timestamp_us']/1e6,0,0,conversion['current_speed_mps'])
    planner=OfflinePlanner(args.instruction)
    result=planner.step(observation,report['candidates'])
    result.update(run=args.run,instruction=args.instruction,
                  input_kind='user_diagnostic_instruction; not assumed to be a doPlan annotation')
    if args.output:
        if '/' in args.output or '\\' in args.output or '..' in args.output:p.error('Output must be a simple filename')
        write_json(ROOT/'runs/project-v2/interactive'/args.output,result)
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
