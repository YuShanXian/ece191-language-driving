"""Illustrate stage tracking with previously extracted causal observations."""
import argparse,json
from mtr_project.paths import ROOT,write_json,sha256
from mtr_project.language import parse_instruction
from mtr_project.stages import Observation,StageMachine

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--instruction',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    source=(ROOT/args.source).resolve();output=(ROOT/args.output).resolve()
    if not source.is_relative_to(ROOT) or not output.is_relative_to(ROOT):raise ValueError('Project paths required')
    if output.exists():raise ValueError('Preserve previous output')
    report=json.loads(source.read_text());program=parse_instruction(args.instruction);machine=StageMachine(program)
    for frame in report['trace']:
        observation=Observation(frame['timestamp_us']/1e6,*frame['xy'],frame['speed_mps'],completed_actions=tuple(frame['observed_actions']))
        frame['stage']=machine.update(observation)
    report.update(instruction=args.instruction,program=program,final_stage=machine.snapshot(),
                  illustration_only=True,instruction_source='Analyst-chosen after observing the recording, for interface demonstration; NOT a doPlan ground-truth command.',
                  source_observation_file=str(source.relative_to(ROOT)),source_observation_sha256=sha256(source))
    write_json(output,report);print(json.dumps(report['final_stage'],indent=2))

if __name__=='__main__':main()
