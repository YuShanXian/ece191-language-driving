"""Run a bounded two-window inference batch, writing a log for each stage."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser();parser.add_argument('--rows',nargs='+',type=int,default=[700,900]);args_cli=parser.parse_args()
manifest=[]
for row in args_cli.rows:
    sample=f'nuplan-gps{row}';run=f'internal-gps{row}'
    stages=[('convert',['scripts/convert_nuplan_mtr.py','--gps-row',str(row),'--output',f'samples/{sample}']),
            ('infer',['scripts/export_mtr_candidates.py','--checkpoint',str(ROOT/'weights/pretrained_weights/checkpoint_for_val_test.ckpt'),
                      '--data',str(ROOT/'samples'/sample),'--output',str(ROOT/'runs'/run),'--ego-only']),
            ('check',['scripts/evaluate_candidate_checks.py','--sample',sample,'--run',run,'--refined'])]
    for stage,args in stages:
        print(f'START gps{row} {stage}',flush=True)
        log=ROOT/'runs'/f'gps{row}-{stage}.log'
        with log.open('w') as f:
            result=subprocess.run([sys.executable,*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        if result.returncode:
            print(log.read_text()[-6000:],flush=True);raise SystemExit(result.returncode)
        print(f'DONE gps{row} {stage}: {log}',flush=True)
    summary=json.loads((ROOT/'runs'/run/'refined_feasibility.json').read_text())['summary']
    manifest.append(summary)
    print(json.dumps(summary),flush=True)
(ROOT/'runs'/('additional-windows-'+'-'.join(map(str,args_cli.rows))+'.json')).write_text(json.dumps(manifest,indent=2))
