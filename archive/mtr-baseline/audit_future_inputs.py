"""GPU regression: future state values and validity are not prediction inputs."""
import argparse,json,pickle,subprocess,sys
import numpy as np
from mtr_project.paths import ROOT,write_json,sha256


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default='baseline-v1');args=parser.parse_args()
    manifest=json.loads((ROOT/f'runs/project-v2/{args.tag}/development-manifest.json').read_text())
    # One predetermined middle window per development recording, not selected by outcome.
    records=[r for r in manifest if r['anchor_fraction']==.5];results=[]
    for record in records:
        source=ROOT/'samples'/record['sample'];sample=ROOT/'samples/project-v2/future-mask-audit'/record['key']
        out=ROOT/'runs/project-v2/future-mask-audit'/record['key'];receipt=out/'audit.json'
        if receipt.exists():results.append(json.loads(receipt.read_text()));continue
        if sample.exists() or out.exists():raise ValueError('Unfinished audit exists; inspect before retrying')
        sample.mkdir(parents=True)
        for file in source.glob('*.pkl'):
            with file.open('rb') as stream:obj=pickle.load(stream)
            if isinstance(obj,dict) and 'tracks' in obj:
                for track in obj['tracks'].values():
                    state=track['state']
                    for name,array in state.items():
                        if name!='timestamps':array[21:]=0
            with (sample/file.name).open('wb') as stream:pickle.dump(obj,stream)
        logs=ROOT/'runs/project-v2/future-mask-audit/logs';logs.mkdir(parents=True,exist_ok=True)
        command=[sys.executable,'scripts/export_mtr_candidates.py','--checkpoint',str(ROOT/'weights/pretrained_weights/checkpoint_for_val_test.ckpt'),
                 '--data',str(sample),'--output',str(out),'--ego-only']
        with (logs/f'{record["key"]}.log').open('w') as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        report={'scene':record['key'],'returncode':result.returncode,
                'perturbation':'All future position, heading, velocity, dimensions, validity and tracking scores set to zero. History, map, timestamps unchanged.',
                'source_sha256':sha256(ROOT/'runs'/record['run']/'internal_0000.npz')}
        if result.returncode==0:
            original=np.load(ROOT/'runs'/record['run']/'internal_0000.npz');masked=np.load(out/'internal_0000.npz')
            differences={key:float(np.max(np.abs(original[key]-masked[key]))) for key in ['world_xy','scores','selected_indices']}
            report.update(maximum_absolute_differences=differences,passed=all(x<=1e-5 for x in differences.values()))
        else:report.update(passed=False,error='Prediction rejected a sample with unavailable future; inspect log')
        out.mkdir(parents=True,exist_ok=True);write_json(receipt,report);results.append(report);print(json.dumps(report),flush=True)
    write_json(ROOT/'runs/project-v2/future-mask-audit/summary.json',{'results':results,'all_passed':all(r['passed'] for r in results),
              'scope':'Three fixed development windows. A regression check, not a proof for every upstream configuration.'})
    if not all(r['passed'] for r in results):raise SystemExit(1)

if __name__=='__main__':main()
