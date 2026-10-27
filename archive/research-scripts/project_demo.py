"""Local-only interactive viewer for real cached MTR candidates and language proposals."""
import argparse
import json
import pickle
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import numpy as np
from mtr_project.paths import ROOT,sha256
from mtr_project.planner import OfflinePlanner
from mtr_project.stages import Observation
from mtr_project.http_ranges import byte_range
from mtr_project.guarded_planner import apply_pool_guard
from mtr_project.tracking_selection import apply_tracking_filter

ALIGNED_CLIP='2021.06.09.12.39.51_veh-26_05332_05540'
ALIGNED_CLIPS=(ALIGNED_CLIP,'2021.06.09.18.23.43_veh-35_00026_00274')

def registry():
    cases={}
    for name in ['internal-moving','internal-lane','internal-stopped','internal-gps130','internal-gps150','internal-gps700','internal-gps900']:
        path=ROOT/'runs'/name/'anchored_feasibility.json'
        if path.exists():cases[name]={'name':name,'run':name,'split':'original exploratory log'}
    base=ROOT/'runs/project-v2/baseline-v1'
    for split in ('development','evaluation'):
        manifest=base/f'{split}-manifest.json'
        if manifest.exists():
            for row in json.loads(manifest.read_text()):
                cases[row['key']]={'name':row['key'],'run':row['run'],'split':split,'clip':row['clip']}
    sequence=ROOT/'runs/project-v2/annotation-sequence-v1/sequence-manifest.json'
    if sequence.exists():
        for row in json.loads(sequence.read_text()):
            cases[row['key']]={'name':row['key'],'run':row['run'],'split':row['split'],'clip':row['clip'],'default_instruction':row['instruction']}
    second_sequence=ROOT/'runs/project-v2/second-annotation-v1/sequence-manifest.json'
    if second_sequence.exists():
        for row in json.loads(second_sequence.read_text()):
            cases[row['key']]={'name':row['key'],'run':row['run'],'split':'second actual annotation exploration','clip':row['clip'],'default_instruction':row['instruction']}
    refined_sequence=ROOT/'runs/project-v2/annotation-sequence-v1/sequence-report-map-tail-v1.json'
    if refined_sequence.exists():
        for row in json.loads(refined_sequence.read_text())['checkpoints']:
            cases[row['key']]={'name':row['key'],'run':row['run'],'split':'map adjustment experiment','clip':row['clip'],'default_instruction':row['instruction']}
    second_refined=ROOT/'runs/project-v2/second-annotation-v1/sequence-report-map-tail-second-v1.json'
    if second_refined.exists():
        for row in json.loads(second_refined.read_text())['checkpoints']:
            cases[row['key']]={'name':row['key'],'run':row['run'],'split':'second annotation map adjustment','clip':row['clip'],'default_instruction':row['instruction']}
    development_adjustment=ROOT/'runs/project-v2/map-tail-development-v1/comparison.json'
    if development_adjustment.exists():
        for row in json.loads(development_adjustment.read_text())['windows_detail']:
            key='map-tail-development-v1--'+row['key']
            cases[key]={'name':key,'run':'project-v2/map-tail-development-v1/'+row['key'],'split':'development map adjustment','clip':row['clip']}
    reserve_path=ROOT/'runs/project-v2/reserve-tail-v1/experiment.json'
    if reserve_path.exists():
        reserve=json.loads(reserve_path.read_text())
        if reserve.get('status')=='completed':
            for row in reserve['windows']:
                key='reserve-tail-v1--'+row['key']
                cases[key]={'name':key,'run':row['run'],'split':'10cm reserve generation experiment',
                    'default_instruction':'Merge to the left lane.' if row['actions'][0]=='lane_change_left' else 'Merge to the right lane.'}
    challenge=ROOT/'runs/project-v2/turn-challenge-v1/evaluation.json'
    verification=challenge.with_name('verification.json')
    if challenge.exists() and verification.exists():
        if sha256(challenge)!=json.loads(verification.read_text())['evaluation_sha256']:raise ValueError('Unverified turn challenge registry')
        for result in json.loads(challenge.read_text())['windows']:
            row=result['window'];key='turn-challenge-v1--'+row['key']
            cases[key]={'name':key,'run':row['run'],'split':'new-recording turn challenge; frozen baseline','clip':row['clip'],'default_instruction':'Turn left.'}
    return cases

@lru_cache(maxsize=32)
def load_case(run):
    folder=ROOT/'runs'/run
    report=json.loads((folder/'anchored_feasibility.json').read_text())
    if run.startswith('project-v2/turn-challenge-v1/'):
        evaluation_path=ROOT/'runs/project-v2/turn-challenge-v1/evaluation.json';verified=json.loads(evaluation_path.with_name('verification.json').read_text())
        if sha256(evaluation_path)!=verified['evaluation_sha256']:raise ValueError('Turn challenge evaluation changed')
        evaluation=json.loads(evaluation_path.read_text())
        for name in ['anchored_feasibility.json','internal_0000.npz','refined_v2_candidates.npz']:
            path=folder/name
            if sha256(path)!=evaluation['source_sha256'][str(path.relative_to(ROOT))]:raise ValueError('Turn challenge candidate output changed')
    if 'reserve_tail_experiment' in report:
        experiment_path=ROOT/'runs/project-v2/reserve-tail-v1/experiment.json';verification_path=experiment_path.with_name('verification.json')
        experiment=json.loads(experiment_path.read_text());verification=json.loads(verification_path.read_text())
        if sha256(experiment_path)!=verification['experiment_sha256']:raise ValueError('Reserve proposal experiment has not been verified')
        window=next((w for w in experiment['windows'] if w['run']==run),None)
        if window is None:raise ValueError('Unknown reserve proposal output')
        for name,expected in window['output_sha256'].items():
            if sha256(folder/name)!=expected:raise ValueError('Verified reserve proposal output changed')
    sample=ROOT/'samples'/report['summary']['sample']
    conversion=json.loads((sample/'conversion.json').read_text())
    data=np.load(folder/'internal_0000.npz');center=data['center']
    with (sample/conversion['scenario']).open('rb') as stream:scenario=pickle.load(stream)
    angle=float(center[6]);c,s=np.cos(angle),np.sin(angle)
    rotation=np.array([[c,-s],[s,c]])
    def local(points):return ((np.asarray(points)[...,:2]-center[:2])@rotation).round(4).tolist()
    roads=[]
    for feature in scenario['map_features'].values():
        if 'polyline' in feature:roads.append(local(feature['polyline']))
    ego=scenario['tracks']['ego']['state']
    payload={'run':run,'summary':report['summary'],'current_speed_mps':conversion['current_speed_mps'],
             'timestamp_us':conversion['current_timestamp_us'],'roads':roads,
             'history':local(ego['position'][:21,:2]),'recorded_future':local(ego['position'][21:81,:2]),
             'raw':local(data['world_xy']),
             'refined':local(np.load(folder/'refined_v2_candidates.npz')['world_xy']),
             'scores':data['scores'].astype(float).tolist(),'candidates':report['candidates'],
             'top_model_candidate':int(np.argmax(data['scores']))+1,
             'original_final_five':[int(x)+1 for x in data['selected_indices']],
             'provenance':{'sample':report['summary']['sample'],'clip':conversion.get('source_clip',conversion['scenario']),
                           'data':'nuPlan structured observations + vector map','weights':'pretrained Valeo4Cast MTR',
                           'language':'controlled grammar v2; no LLM or trained language model',
                           'map_adjustment_experiment':'map_tail_experiment' in report or 'reserve_tail_experiment' in report,
                           'reserve_generation':({'actions':report['reserve_tail_experiment']['actions'],'target_reserve_m':report['reserve_tail_experiment']['target_reserve_m']} if 'reserve_tail_experiment' in report else None),
                           'processing':report['summary'].get('prediction_source'),
                           'route_assumption':report.get('experimental_route_policy',{}).get('scope')}}
    audit_path=ROOT/'runs/project-v2/heading-sensitivity-v1/audit.json'
    if audit_path.exists():
        audit=json.loads(audit_path.read_text());audited=[r for r in audit['rows'] if r['run']==run]
        if audited:
            for name in ['anchored_feasibility.json','refined_v2_candidates.npz','internal_0000.npz']:
                path=folder/name
                if sha256(path)!=audit['source_sha256'][str(path.relative_to(ROOT))]:raise ValueError('Heading diagnostic refers to different candidate data')
        payload['heading_diagnostic']={'by_candidate':{str(r['candidate']):r for r in audited},
            'audited_count':len(audited),'scope':'Alternative body-heading sensitivity only; this does not replace the original selection or establish executable control.'}
    pool_path=ROOT/'runs/project-v2/heading-pool-v1/audit.json'
    if pool_path.exists():
        pool=json.loads(pool_path.read_text());window=next((w for w in pool['windows'] if w['run']==run),None)
        if window is not None:
            for name in ['anchored_feasibility.json','refined_v2_candidates.npz','internal_0000.npz']:
                path=folder/name
                if sha256(path)!=pool['source_sha256'][str(path.relative_to(ROOT))]:raise ValueError('Complete-pool diagnostic refers to different candidates')
            payload['geometry_pool']={'audited_candidates':window['audited_candidates'],'margins_m':pool['specification']['margins_m']}
    tracking_path=ROOT/'runs/project-v2/tracking-diagnostic-v1/report-summary.json'
    if tracking_path.exists() and 'reserve_tail_experiment' in report:
        tracking=json.loads(tracking_path.read_text());audit_path=tracking_path.with_name('experiment.json');verified_path=tracking_path.with_name('verification.json')
        if sha256(audit_path)!=tracking['experiment_sha256'] or sha256(verified_path)!=tracking['verification_sha256']:raise ValueError('Tracking summary refers to unverified output')
        tracking_audit=json.loads(audit_path.read_text());entries=[r for r in tracking['proposals'] if 'project-v2/reserve-tail-v1/'+r['window']==run]
        if entries:
            for name in ['anchored_feasibility.json','refined_v2_candidates.npz','internal_0000.npz']:
                path=folder/name
                if sha256(path)!=tracking_audit['source_sha256'][str(path.relative_to(ROOT))]:raise ValueError('Tracking diagnostic uses different proposals')
            lookup={}
            for row in entries:
                nominal=row['nominal_dt005_zero_angle'];array_path=ROOT/nominal['arrays'];saved=next(r for r in tracking_audit['results'] if r['arrays']==nominal['arrays'])
                if sha256(array_path)!=saved['arrays_sha256']:raise ValueError('Tracking trajectory changed')
                rollouts=[r for r in tracking_audit['results'] if r['window']==row['window'] and r['candidate']==row['candidate']]
                lookup[str(row['candidate'])]={**row,'rollouts':rollouts,'simulated_center_local':local(np.load(array_path)['center_xy'])}
            payload['tracking_diagnostic']={'by_candidate':lookup,'scope':tracking['scope'],'display_assumptions':'Zero initial tire angle;0.05s integration; official LQR; fixed6s path.'}
    turn_tracking=ROOT/'runs/project-v2/turn-tracking-v1/report-summary.json'
    if turn_tracking.exists() and run.startswith('project-v2/turn-challenge-v1/'):
        tracking=json.loads(turn_tracking.read_text());experiment_path=turn_tracking.with_name('experiment.json');verified_path=turn_tracking.with_name('verification.json')
        if sha256(experiment_path)!=tracking['experiment_sha256'] or sha256(verified_path)!=tracking['verification_sha256']:raise ValueError('Turn tracking report is not verified')
        tracked_experiment=json.loads(experiment_path.read_text());parent_name='runs/project-v2/turn-challenge-v1/evaluation.json'
        if sha256(ROOT/parent_name)!=tracked_experiment['source_sha256'][parent_name]:raise ValueError('Turn tracking uses a different challenge evaluation')
        entries=[r for r in tracking['proposals'] if r['window']['run']==run];lookup={}
        for row in entries:
            array_path=ROOT/row['nominal_arrays']
            if sha256(array_path)!=row['nominal_arrays_sha256']:raise ValueError('Turn tracking trajectory changed')
            lookup[str(row['candidate'])]={**row,'simulated_center_local':local(np.load(array_path)['center_xy'])}
        if lookup:payload['turn_tracking_diagnostic']={'by_candidate':lookup,'scope':tracking['scope'],'update_interval_note':tracking['update_interval_note']}
    comparison_path=ROOT/'runs/project-v2/controller-comparison-v1/experiment.json'
    if comparison_path.exists():
        comparison=json.loads(comparison_path.read_text());verification_path=comparison_path.with_name('verification.json')
        verification=json.loads(verification_path.read_text())
        if verification['experiment_sha256']!=sha256(comparison_path):raise ValueError('Controller comparison is not verified')
        proposals=[p for p in comparison['population'] if p['window']['run']==run];lookup={}
        for p in proposals:
            if sha256(ROOT/p['screen'])!=comparison['source_sha256'][p['screen']]:raise ValueError('Controller comparison uses another candidate screen')
            entries=[r for r in comparison['results'] if r['proposal']==p['key']]
            controllers={}
            for name in comparison['specification']['controllers']:
                trials=[r for r in entries if r['controller']==name];completed=[r for r in trials if r['status']=='completed']
                controllers[name]={'completed':len(completed),'total':len(trials),'road_passed':sum(r['simulated_pose_checks']['body_passed'] for r in completed),
                    'maximum_error_range_m':[min(r['metrics']['maximum_center_error_m'] for r in completed),max(r['metrics']['maximum_center_error_m'] for r in completed)] if completed else None}
            lookup[str(p['candidate'])]=controllers
        if lookup:payload['controller_comparison']={'by_candidate':lookup,'duration_seconds':comparison['specification']['simulation_duration_seconds'],'scope':comparison['scope']}
        terminal_path=ROOT/'runs/project-v2/controller-terminal-hold-v1/experiment.json'
        if lookup and terminal_path.exists():
            terminal=json.loads(terminal_path.read_text());verified=json.loads(terminal_path.with_name('verification.json').read_text())
            if verified['experiment_sha256']!=sha256(terminal_path) or terminal['parent_experiment_sha256']!=sha256(comparison_path):raise ValueError('Terminal-hold result is not verified against this comparison')
            terminal_lookup={}
            for p in proposals:
                entries=[r for r in terminal['results'] if r.get('proposal')==p['key']]
                terminal_lookup[str(p['candidate'])]={name:{'completed':sum(r['status']=='completed_terminal_hold' for r in entries if r['controller']==name),
                    'road_passed':sum(r['simulated_pose_checks']['body_passed'] for r in entries if r['controller']==name)} for name in comparison['specification']['controllers']}
            payload['controller_terminal_hold']={'by_candidate':terminal_lookup,'scope':terminal['scope']}
    traffic_path=ROOT/'runs/project-v2/traffic-context-v1/audit.json'
    if traffic_path.exists() and run.startswith('project-v2/turn-challenge-v1/'):
        traffic=json.loads(traffic_path.read_text());verification=json.loads(traffic_path.with_name('verification.json').read_text())
        if verification['audit_sha256']!=sha256(traffic_path):raise ValueError('Traffic context is not verified')
        window=next((w for w in traffic['windows'] if w['window']['run']==run),None)
        if window is None:raise ValueError('Traffic audit missing this challenge window')
        for file in [folder/'anchored_feasibility.json',sample/'conversion.json']:
            if sha256(file)!=traffic['source_sha256'][str(file.relative_to(ROOT))]:raise ValueError('Traffic context refers to another scene')
        payload['traffic_context']={'by_candidate':{str(r['candidate']):r['context'] for r in window['candidates']},
            'current_signal_connector_count':window['current_signal_connector_count'],'scope':traffic['scope']}
    stops_path=ROOT/'runs/project-v2/stop-region-geometry-v1/audit.json'
    if stops_path.exists() and run.startswith('project-v2/turn-challenge-v1/'):
        stops=json.loads(stops_path.read_text());verified=json.loads(stops_path.with_name('verification.json').read_text())
        if verified['audit_sha256']!=sha256(stops_path):raise ValueError('Stop-region audit is not verified')
        if sha256(traffic_path)!=stops['source_sha256'][str(traffic_path.relative_to(ROOT))]:raise ValueError('Stop-region audit uses different signal context')
        for file in [folder/'refined_v2_candidates.npz',folder/'internal_0000.npz',sample/'conversion.json']:
            if sha256(file)!=stops['source_sha256'][str(file.relative_to(ROOT))]:raise ValueError('Stop-region audit refers to another path')
        window=next(w for w in stops['windows'] if w['window']['run']==run)
        payload['stop_region_geometry']={'by_candidate':{str(c['candidate']):c for c in window['candidates']},'scope':stops['scope']}
    return payload

class Handler(BaseHTTPRequestHandler):
    def send_video(self,path):
        size=path.stat().st_size
        try:start,end,partial=byte_range(self.headers.get('Range'),size)
        except ValueError:
            self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
        self.send_response(206 if partial else 200);self.send_header('Content-Type','video/mp4')
        self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
        if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        try:
            with path.open('rb') as stream:
                stream.seek(start);remaining=end-start+1
                while remaining:
                    chunk=stream.read(min(65536,remaining))
                    if not chunk:break
                    self.wfile.write(chunk);remaining-=len(chunk)
        except (BrokenPipeError,ConnectionResetError):pass
    def send_json(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        url=urlparse(self.path)
        if url.path=='/api/health':self.send_json({'project':'ECE191-MTR','version':'offline-v2','root':str(ROOT)});return
        if url.path=='/report':
            self.send_response(302);self.send_header('Location','/report/');self.end_headers();return
        report_files={'/report/':('index.html','text/html; charset=utf-8'),
                      '/report/baseline-overview.png':('baseline-overview.png','image/png'),
                      '/report/baseline-overview.pdf':('baseline-overview.pdf','application/pdf'),
                      '/report/annotation-experiment.png':('annotation-experiment.png','image/png'),
                      '/report/annotation-experiment.pdf':('annotation-experiment.pdf','application/pdf'),
                      '/report/second-annotation-experiment.png':('second-annotation-experiment.png','image/png'),
                      '/report/second-annotation-experiment.pdf':('second-annotation-experiment.pdf','application/pdf'),
                      '/report/kinematic-diagnostic.png':('kinematic-diagnostic.png','image/png'),
                      '/report/kinematic-diagnostic.pdf':('kinematic-diagnostic.pdf','application/pdf'),
                      '/report/heading-sensitivity.png':('heading-sensitivity.png','image/png'),
                      '/report/heading-sensitivity.pdf':('heading-sensitivity.pdf','application/pdf'),
                      '/report/heading-pool-comparison.png':('heading-pool-comparison.png','image/png'),
                      '/report/heading-pool-comparison.pdf':('heading-pool-comparison.pdf','application/pdf'),
                      '/report/reserve-tail-comparison.png':('reserve-tail-comparison.png','image/png'),
                      '/report/reserve-tail-comparison.pdf':('reserve-tail-comparison.pdf','application/pdf'),
                      '/report/tracking-diagnostic.png':('tracking-diagnostic.png','image/png'),
                      '/report/tracking-diagnostic.pdf':('tracking-diagnostic.pdf','application/pdf'),
                      '/report/tracking-example.png':('tracking-example.png','image/png'),
                      '/report/tracking-example.pdf':('tracking-example.pdf','application/pdf'),
                      '/report/turn-challenge-coverage.png':('turn-challenge-coverage.png','image/png'),
                      '/report/turn-challenge-coverage.pdf':('turn-challenge-coverage.pdf','application/pdf'),
                      '/report/turn-challenge-examples.png':('turn-challenge-examples.png','image/png'),
                      '/report/turn-challenge-examples.pdf':('turn-challenge-examples.pdf','application/pdf'),
                      '/report/turn-tracking.png':('turn-tracking.png','image/png'),
                      '/report/turn-tracking.pdf':('turn-tracking.pdf','application/pdf'),
                      '/report/multirate-tracking.png':('multirate-tracking.png','image/png'),
                      '/report/multirate-tracking.pdf':('multirate-tracking.pdf','application/pdf'),
                      '/report/controller-comparison.png':('controller-comparison.png','image/png'),
                      '/report/controller-comparison.pdf':('controller-comparison.pdf','application/pdf'),
                      '/report/controller-turn-comparison.png':('controller-turn-comparison.png','image/png'),
                      '/report/controller-turn-comparison.pdf':('controller-turn-comparison.pdf','application/pdf'),
                      '/report/controller-terminal-hold.png':('controller-terminal-hold.png','image/png'),
                      '/report/controller-terminal-hold.pdf':('controller-terminal-hold.pdf','application/pdf'),
                      '/report/stop-region-geometry.png':('stop-region-geometry.png','image/png'),
                      '/report/stop-region-geometry.pdf':('stop-region-geometry.pdf','application/pdf')}
        if url.path in report_files:
            name,mime=report_files[url.path];file=ROOT/'runs/project-v2/reports'/name
            if not file.exists():self.send_json({'error':'Report not generated yet'},404);return
            content=file.read_bytes();self.send_response(200);self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
        raw_comparison_files={'/raw-comparison/':('index.html','text/html; charset=utf-8')}
        for clip in ALIGNED_CLIPS:
            name=clip+'-comparison.png';raw_comparison_files['/raw-comparison/'+name]=(name,'image/png')
        if url.path=='/raw-comparison':
            self.send_response(302);self.send_header('Location','/raw-comparison/');self.end_headers();return
        if url.path in raw_comparison_files:
            name,mime=raw_comparison_files[url.path];file=ROOT/'runs/project-v2/raw-image-comparison-v1'/name
            if not file.exists():self.send_json({'error':'Raw-image comparison not generated yet'},404);return
            content=file.read_bytes();self.send_response(200);self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
        if url.path in ('/','/replay','/alignment'):
            name={'/':'index.html','/replay':'replay.html','/alignment':'alignment.html'}[url.path]
            content=(ROOT/'scripts/mtr_project/web'/name).read_bytes()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
        if url.path=='/api/scenes':self.send_json(list(registry().values()));return
        if url.path=='/api/aligned-clips':
            self.send_json([{'clip':clip} for clip in ALIGNED_CLIPS if (ROOT/'runs/project-v2/video-alignment'/clip/'viewer-alignment.json').exists()]);return
        if url.path=='/api/alignment':
            clip=parse_qs(url.query).get('clip',[ALIGNED_CLIP])[0]
            if clip not in ALIGNED_CLIPS:self.send_json({'error':'Unknown aligned clip'},404);return
            folder=ROOT/'runs/project-v2/video-alignment'/clip
            file=folder/'viewer-alignment.json'
            if not file.exists():self.send_json({'error':'Alignment viewer data not prepared'},404);return
            evidence=json.loads(file.read_text())
            self.send_json({'alignment':evidence,'videos':evidence['videos']});return
        if url.path.startswith('/video/'):
            name=url.path.removeprefix('/video/')
            if name not in {x+'.mp4' for x in ['F0','B0','L0','L1','L2','R0','R1','R2','gps_map']}:
                self.send_json({'error':'Unknown video'},404);return
            clip=parse_qs(url.query).get('clip',[ALIGNED_CLIP])[0]
            if clip not in ALIGNED_CLIPS:self.send_json({'error':'Unknown aligned clip'},404);return
            path=ROOT/'data/doplan'/clip/name
            if name=='gps_map.mp4':
                derived=ROOT/'runs/project-v2/web-video'/clip/name
                if derived.exists() and (derived.parent/'conversion-receipt.json').exists():path=derived
            if not path.exists():self.send_json({'error':'Video has not been downloaded'},404);return
            self.send_video(path);return
        if url.path=='/api/replays':
            files=sorted((ROOT/'runs/project-v2/replay').glob('*.json'))
            self.send_json([{'id':p.stem} for p in files]);return
        if url.path=='/api/replay':
            files={p.stem:p for p in (ROOT/'runs/project-v2/replay').glob('*.json')}
            path=files.get(parse_qs(url.query).get('id',[''])[0])
            if path is None:self.send_json({'error':'Unknown replay'},404);return
            self.send_json(json.loads(path.read_text()));return
        if url.path=='/api/scene':
            key=parse_qs(url.query).get('id',[''])[0];entry=registry().get(key)
            if entry is None:self.send_json({'error':'Unknown scene'},404);return
            try:self.send_json(load_case(entry['run']))
            except (OSError,ValueError,KeyError) as exc:self.send_json({'error':str(exc)},500)
            return
        self.send_json({'error':'Not found'},404)
    def do_POST(self):
        if self.path!='/api/plan':self.send_json({'error':'Not found'},404);return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16384:raise ValueError('Invalid request size')
            request=json.loads(self.rfile.read(length))
            if not isinstance(request,dict) or not isinstance(request.get('scene'),str):raise ValueError('Scene must be a string in a JSON object')
            entry=registry().get(request['scene'])
            if entry is None:raise ValueError('Unknown scene')
            instruction=request.get('instruction')
            if not isinstance(instruction,str) or len(instruction)>2000:raise ValueError('Invalid instruction')
            case=load_case(entry['run'])
            result=OfflinePlanner(instruction).step(Observation(case['timestamp_us']/1e6,0,0,case['current_speed_mps']),case['candidates'])
            if case['provenance']['reserve_generation']:result['selection_context']='reserve_generation'
            margin=request.get('geometry_margin')
            tracking_filter=request.get('tracking_filter',False)
            if type(tracking_filter) is not bool:raise ValueError('tracking_filter must be a boolean')
            if tracking_filter and margin is not None:raise ValueError('Compare one additional selection experiment at a time')
            if margin is not None:result=apply_pool_guard(result,case['candidates'],case.get('geometry_pool'),margin,case['current_speed_mps'])
            if tracking_filter:result=apply_tracking_filter(result,case['candidates'],case.get('tracking_diagnostic'),case['current_speed_mps'])
            self.send_json(result)
        except (ValueError,KeyError,json.JSONDecodeError) as exc:self.send_json({'error':str(exc)},400)
    def log_message(self,fmt,*args):print(fmt%args,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);args=p.parse_args()
    print(f'Open http://localhost:{args.port} — local offline demo; Ctrl+C to stop.',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
