"""One local entry point for tests, evidence audits, and report reconstruction."""
import argparse,json,subprocess,sys,time
from datetime import datetime,timezone
from mtr_project.paths import ROOT,sha256,write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-reports',action='store_true',help='Regenerate figures and HTML from cached results; no model inference')
    parser.add_argument('--environment',action='store_true',help='Also run CUDA/import preflight (tiny GPU tensor check)')
    args=parser.parse_args();stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder=ROOT/'runs/project-v2/verification'/stamp;folder.mkdir(parents=True,exist_ok=False)
    steps=[('tests',['-m','unittest','discover','-s','tests']),('dependencies',['-m','pip','check']),
           ('saved-evidence',['scripts/verify_saved_project.py']),('sequence-cache',['scripts/audit_sequence_cache.py','--tag','second-annotation-v1'])]
    if (ROOT/'runs/project-v2/raw-image-comparison-v1/comparison.json').exists():
        steps.append(('raw-image-evidence',['scripts/verify_raw_camera_comparison.py']))
    if (ROOT/'runs/project-v2/tracking-diagnostic-v1/experiment.json').exists():
        steps.append(('tracking-evidence',['scripts/verify_tracking_diagnostic.py']))
    if (ROOT/'runs/project-v2/tracking-selection-v1/evaluation.json').exists():
        steps.append(('tracking-selection',['scripts/verify_tracking_selection.py']))
    if (ROOT/'runs/project-v2/turn-challenge-v1/evaluation.json').exists():
        steps.extend([('turn-challenge-cache',['scripts/run_turn_challenge.py','--cached-only']),
                      ('turn-challenge-selection',['scripts/verify_turn_challenge.py'])])
    if (ROOT/'runs/project-v2/turn-tracking-v1/experiment.json').exists():
        steps.append(('turn-tracking',['scripts/verify_turn_tracking.py']))
    if (ROOT/'runs/project-v2/multirate-tracking-v1/experiment.json').exists():
        steps.append(('multirate-tracking',['scripts/verify_multirate_tracking.py']))
    if (ROOT/'runs/project-v2/controller-comparison-v1/experiment.json').exists():
        steps.append(('controller-comparison',['scripts/verify_controller_comparison.py']))
    if (ROOT/'runs/project-v2/traffic-context-v1/audit.json').exists():
        steps.append(('traffic-context',['scripts/audit_traffic_context.py','--verify']))
    if (ROOT/'runs/project-v2/controller-terminal-hold-v1/experiment.json').exists():
        steps.append(('controller-terminal-hold',['scripts/run_terminal_hold.py','--verify']))
    if (ROOT/'runs/project-v2/stop-region-geometry-v1/audit.json').exists():
        steps.append(('stop-region-geometry',['scripts/audit_stop_regions.py','--verify']))
    if args.environment:steps.append(('environment',['scripts/preflight.py']))
    if args.refresh_reports:
        steps.extend((name,['scripts/'+script]) for name,script in [
            ('development-comparison','summarize_map_tail_development.py'),('original-figure','report_annotation_experiment.py'),
            ('second-figure','report_second_annotation.py'),('kinematic-figure','report_kinematic_diagnostic.py'),
            ('heading-figure','report_heading_sensitivity.py'),('complete-pool-figure','report_heading_pool.py'),
            ('reserve-proposal-figure','report_reserve_tail.py')])
        if (ROOT/'runs/project-v2/tracking-diagnostic-v1/experiment.json').exists():
            steps.append(('tracking-figures',['scripts/report_tracking_diagnostic.py']))
        if (ROOT/'runs/project-v2/turn-challenge-v1/evaluation.json').exists():
            steps.append(('turn-challenge-figures',['scripts/report_turn_challenge.py']))
        if (ROOT/'runs/project-v2/turn-tracking-v1/experiment.json').exists():
            steps.append(('turn-tracking-figure',['scripts/report_turn_tracking.py']))
        if (ROOT/'runs/project-v2/multirate-tracking-v1/experiment.json').exists():
            steps.append(('multirate-tracking-figure',['scripts/report_multirate_tracking.py']))
        if (ROOT/'runs/project-v2/controller-comparison-v1/experiment.json').exists():
            steps.append(('controller-comparison-figures',['scripts/report_controller_comparison.py']))
        if (ROOT/'runs/project-v2/controller-terminal-hold-v1/experiment.json').exists():
            steps.append(('controller-terminal-hold-figure',['scripts/report_terminal_hold.py']))
        if (ROOT/'runs/project-v2/stop-region-geometry-v1/audit.json').exists():
            steps.append(('stop-region-figure',['scripts/report_stop_regions.py']))
        steps.append(('html-report',['scripts/report_project_results.py']))
    result={'started_utc':stamp,'generator_sha256':sha256(__file__),'steps':[],
        'scope':'Repeatability on this installed machine. Uses cached MTR outputs; does not train, rerun inference, or certify a fresh installation.'}
    for name,command in steps:
        started=time.monotonic();print('CHECK',name,flush=True);log=folder/(name+'.log')
        with log.open('w') as stream:process=subprocess.run([sys.executable,*command],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        result['steps'].append({'name':name,'command':command,'returncode':process.returncode,'seconds':round(time.monotonic()-started,3),'log':str(log.relative_to(ROOT)),'log_sha256':sha256(log)})
        result['status']='failed' if process.returncode else 'in_progress';write_json(folder/'verification.json',result)
        if process.returncode:print(log.read_text()[-5000:]);raise SystemExit(process.returncode)
    result['status']='passed_declared_checks';write_json(folder/'verification.json',result)
    print(json.dumps({'status':result['status'],'steps':len(steps),'receipt':str(folder/'verification.json')},indent=2))


if __name__=='__main__':main()
