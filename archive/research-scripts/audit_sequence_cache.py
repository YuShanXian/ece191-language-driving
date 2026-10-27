"""Persist a read-only integrity audit of every saved sequence stage receipt."""
import argparse,hashlib,json,re
from mtr_project.paths import ROOT,sha256,write_json
from run_project_pipeline import output_hashes


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.tag):raise ValueError('Simple tag required')
    base=ROOT/'runs/project-v2'/args.tag;manifest=base/'sequence-manifest.json';entries=json.loads(manifest.read_text());verified=[]
    config=json.loads((base/'sequence-config.json').read_text())
    if len(entries)!=len(config['frames']):raise ValueError('Sequence manifest incomplete')
    for entry in entries:
        for step in ['convert','infer','check']:
            path=base/'execution'/entry['key']/(step+'.json');receipt=json.loads(path.read_text())
            if receipt['returncode'] or receipt.get('output_validation_error') or not receipt.get('output_sha256'):raise ValueError('No verified successful output receipt')
            expected=hashlib.sha256(json.dumps({'command':receipt['command'],'inputs':receipt['inputs']},sort_keys=True).encode()).hexdigest()
            if expected!=receipt['fingerprint']:raise ValueError('Receipt fingerprint inconsistent')
            actual=output_hashes(receipt['outputs'])
            if actual!=receipt['output_sha256']:raise ValueError('Stage output changed')
            verified.append({'key':entry['key'],'stage':step,'output_files':len(actual),'receipt_sha256':sha256(path)})
    result={'tag':args.tag,'windows':len(entries),'verified_stages':verified,'manifest_sha256':sha256(manifest),
        'configuration_sha256':sha256(base/'sequence-config.json'),'auditor_sha256':sha256(__file__),
        'scope':'Current output bytes match saved successful-stage receipts. This does not certify a fresh-machine installation or exact GPU rerun determinism.'}
    write_json(base/'cache-integrity-audit.json',result)
    print(json.dumps({'windows':len(entries),'verified_stages':len(verified),'output_files':sum(r['output_files'] for r in verified)}))


if __name__=='__main__':main()
