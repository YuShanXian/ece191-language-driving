"""Data check -> environment -> cached/new MTR pipeline -> evaluation -> per-tag report."""
import argparse,json,re
from datetime import datetime,timezone
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.workflow import SPLITS,validate_tag,expected_records,inspect_data,run_steps,collect_outputs


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',default='baseline-v1')
    p.add_argument('--compute-missing',action='store_true',help='Allow missing conversion, GPU inference and screening stages; never train or overwrite conflicting receipts')
    args=p.parse_args();validate_tag(args.tag)
    config=json.loads((ROOT/'config/project-v2-scenes.json').read_text());expected=expected_records(config,args.tag)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder=ROOT/'runs/project-v2'/args.tag/'workflows'/stamp;folder.mkdir(parents=True,exist_ok=False)
    receipt={'started_utc':stamp,'tag':args.tag,'compute_missing':args.compute_missing,
        'scope':'Fixed-fraction multi-recording offline workflow on this installed machine. No training, closed-loop execution or confirmed language accuracy.'}
    try:
        print('WORKFLOW data-and-source-check',flush=True);receipt['inputs']=inspect_data(ROOT,config,args.tag)
        receipt['implementation_sha256']={str(x.relative_to(ROOT)):sha256(x) for x in sorted((ROOT/'scripts').rglob('*.py'))}
        steps=[('tests',['-m','unittest','discover','-s','tests']),('dependencies',['-m','pip','check']),('environment',['scripts/preflight.py'])]
        for split in SPLITS:
            command=['scripts/run_project_pipeline.py','--tag',args.tag,'--split',split]
            if not args.compute_missing:command.append('--cached-only')
            steps.extend([(split+'-pipeline',command),(split+'-evaluation',['scripts/evaluate_project.py','--tag',args.tag,'--split',split])])
        steps.append(('report',['scripts/report_offline_run.py','--tag',args.tag]))
        run_steps(ROOT,folder,steps,receipt)
        receipt['output_sha256']=collect_outputs(ROOT,args.tag,expected)
        report=ROOT/'runs/project-v2'/args.tag/'report/index.html';receipt['output_sha256'][str(report.relative_to(ROOT))]=sha256(report)
        receipt['pipeline_execution']={}
        for split in SPLITS:
            log=(folder/(split+'-pipeline.log')).read_text()
            receipt['pipeline_execution'][split]={'cached_stages':len(re.findall(r'^CACHED ',log,re.M)),
                'legacy_cached_stages':len(re.findall(r'^CACHED \(legacy receipt;',log,re.M)),
                'new_stages':len(re.findall(r'^START ',log,re.M))}
        # Detect source edits during the workflow instead of labeling a mixed run reproducible.
        for mapping in [receipt['inputs']['source_sha256'],receipt['implementation_sha256']]:
            for name,digest in mapping.items():
                if sha256(ROOT/name)!=digest:raise ValueError('Source changed during workflow: '+name)
        receipt['status']='completed_declared_offline_workflow';write_json(folder/'workflow.json',receipt)
        print(json.dumps({'status':receipt['status'],'pipeline_execution':receipt['pipeline_execution'],'report':str(report),'receipt':str(folder/'workflow.json')},indent=2))
    except Exception as exc:
        receipt.update(status='failed',error=str(exc));write_json(folder/'workflow.json',receipt);raise


if __name__=='__main__':main()
