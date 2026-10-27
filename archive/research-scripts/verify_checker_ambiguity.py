import json,pickle,numpy as np
from datetime import datetime,timezone
from evaluate_candidate_checks import load_graph
from mtr_project.paths import ROOT,write_json,sha256
source=ROOT/'runs/project-v3/scene-context/20261019T072018Z/audit.json';a=json.loads(source.read_text());rows=[]
for r in a['windows']:
 folder=ROOT/'samples'/r['window']['sample'];c=json.loads((folder/'conversion.json').read_text());e=pickle.load(open(folder/c['scenario'],'rb'))['tracks']['ego']['state'];g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map'])
 history=g.match(e['position'][:21,:2],float(e['heading'][0]),return_end_states=True);starts={p['node'] for p in history.get('viable_end_states',[])}
 route=g.match(e['position'][20:81,:2],float(e['heading'][20]),start_nodes=starts);body=g.body_check(e['position'][20:81,:2],float(e['heading'][20]),float(e['length'][20]),float(e['width'][20]),diagnostics=True)
 rows.append({'key':r['key'],'old_match':r['recorded_future_match']['matched'],'new_match':route['matched'],'starts':sorted(starts),'body':body})
summary={'windows':len(rows),'old_matches':sum(r['old_match'] for r in rows),'new_matches':sum(r['new_match'] for r in rows),'body_passes':sum(r['body']['passed'] for r in rows)}
out=ROOT/'runs/project-v3/checker-diagnosis'/('regression-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(parents=True);write_json(out/'results.json',{'summary':summary,'rows':rows,'source_sha256':sha256(source),'checker_sha256':sha256(ROOT/'scripts/trajectory_checks.py')});print(json.dumps({'out':str(out),'summary':summary}),flush=True)
