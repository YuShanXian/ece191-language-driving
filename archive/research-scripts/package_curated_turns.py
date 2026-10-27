"""Validate and package curated recorded-turn cases without MTR-based selection."""
import json,subprocess,sys,pickle
from datetime import datetime,timezone
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from evaluate_candidate_checks import load_graph
from trajectory_checks import footprint
from mtr_project.paths import ROOT,sha256,write_json

def main():
 source=ROOT/'runs/project-v3/curated-turn-windows/20261019T072729Z/selection.json';a=json.loads(source.read_text());groups=defaultdict(list)
 for r in a['candidates']:
  if r['accepted']:groups[(r['clip'],r['event'])].append(r)
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=ROOT/'runs/project-v3/curated-turn-windows'/('validated-'+stamp);out.mkdir(parents=True)
 rows=[]
 for number,group in enumerate(groups.values(),1):
  r=max(group,key=lambda r:(min(abs(r['future_heading_deg']),90)+4*min(r['speed_mps'],5),-r['seconds']))
  sample='project-v3/curated-turns-'+stamp+'/'+f'{number:02d}-{r["action"]}'
  command=[sys.executable,str(ROOT/'scripts/convert_nuplan_mtr.py'),'--db',str(ROOT/r['source_db']),'--timestamp-us',str(r['timestamp_us']),'--output','samples/'+sample]
  process=subprocess.run(command,capture_output=True,text=True)
  (out/(f'{number:02d}-conversion.log')).write_text(process.stdout+process.stderr)
  if process.returncode:raise RuntimeError('Conversion failed '+sample)
  folder=ROOT/'samples'/sample;c=json.loads((folder/'conversion.json').read_text());e=pickle.load(open(folder/c['scenario'],'rb'))['tracks']['ego']['state'];xy=e['position'][:,:2];h=e['heading']
  g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);history=g.match(xy[:21],h[0],return_end_states=True);starts={s['node'] for s in history.get('viable_end_states',[])}
  route=g.match(xy[20:],h[20],start_nodes=starts);body=g.body_check(xy[20:],h[20],float(e['length'][20]),float(e['width'][20]),diagnostics=True)
  actual_body_max=max(footprint(p,theta,float(e['length'][20]),float(e['width'][20])).difference(g.surface).area for p,theta in zip(xy[20:],h[20:]))
  expected={t['connector'] for t in r['near_turns']};on_expected=bool(expected.intersection(route.get('route',[])))
  if not(history['matched'] and route['matched'] and body['passed'] and on_expected):raise ValueError('Validation disagreement '+sample)
  row={**r,'number':number,'sample':sample,'past_only_start_nodes':sorted(starts),'validated_route':route,'validated_body':body,'recorded_heading_body_max_outside_area_m2':actual_body_max,'actual_route_uses_expected_turn':on_expected,'sample_sha256':{str(p.relative_to(ROOT)):sha256(p) for p in folder.iterdir() if p.is_file()}}
  rows.append(row)
  rotation=np.array([[np.cos(h[20]),-np.sin(h[20])],[np.sin(h[20]),np.cos(h[20])]])
  local=lambda p:np.asarray(p)[:,:2]@rotation
  fig,ax=plt.subplots(figsize=(7,6))
  for n in g.nodes.values():
   p=local(n.baseline.coords);ax.plot(p[:,0],p[:,1],color='#dce2e7',lw=.7)
  for key in route['route']:
   p=local(g.nodes[key].baseline.coords);ax.plot(p[:,0],p[:,1],color='#98b7c8',lw=2)
  past=local(xy[:21]);future=local(xy[20:]);ax.plot(past[:,0],past[:,1],color='#25344b',lw=2,label='Observed past: 2 s');ax.plot(future[:,0],future[:,1],color='#1d8f79' if r['action']=='right' else '#8855a0',lw=3,label='Recorded future: 6 s')
  ax.scatter(0,0,s=40,color='#e89a36',zorder=5,label='Current position')
  for t in (2,4,6):
   p=future[t*10];ax.scatter(*p,color='#25344b',s=12);ax.annotate(f'+{t}s',p,xytext=(4,5),textcoords='offset points',fontsize=8)
  points=np.vstack([past,future]);lo=points.min(axis=0)-12;hi=points.max(axis=0)+12;ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_aspect('equal');ax.grid(alpha=.15)
  ax.set_xlabel('Forward (m)');ax.set_ylabel('Left (m)');ax.set_title(f"{number:02d} | {r['action'].upper()} | {r['seconds']:.2f} s in log\nSpeed {r['speed_mps']:.1f} m/s; future heading change {r['future_heading_deg']:.1f} deg",fontsize=11);ax.legend(fontsize=8)
  fig.text(.05,.015,'Recorded driving for case selection; this is NOT an MTR prediction.',fontsize=8);fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(out/f'{number:02d}-{r["action"]}.png',dpi=160);plt.close(fig)
  print(json.dumps({k:row[k] for k in ['number','seconds','action','speed_mps','future_heading_deg','sample']}),flush=True)
  write_json(out/'progress.json',rows)
 report={'selection_source_sha256':sha256(source),'selection_source':str(source.relative_to(ROOT)),'selection_rule':'One per event; maximize min(abs(6s heading),90)+4*min(current speed,5), ties earlier. Selected before MTR inference. Partial turns retained and labeled.','scope':'Exploratory retrospective cases, not an unbiased benchmark or safety validation. Both original and ambiguity-aware route checks pass. Strict body threshold unchanged.','implementation_sha256':{name:sha256(ROOT/name) for name in ['scripts/package_curated_turns.py','scripts/trajectory_checks.py','scripts/mtr_project/screening.py','scripts/convert_nuplan_mtr.py','scripts/evaluate_candidate_checks.py']},'windows':rows,'source_inventory':a['inventory']}
 write_json(out/'manifest.json',report)
 html=['<!doctype html><meta charset="utf-8"><title>Curated turn windows</title><style>body{font:17px Arial;max-width:1000px;margin:40px auto;color:#25344b}img{max-width:100%}section{border-top:1px solid #ccc;margin-top:30px}</style><h1>7 curated turn events: 5 left, 2 right</h1><p>Scanned 11 local logs; inspected 40 anchors; 14 passed, deduplicated to 7 events. Recorded driving, not MTR outputs. Strict map/body checks pass; no claim of collision or signal legality.</p>']
 for r in rows:html.append(f'<section><h2>{r["number"]:02d}: {r["action"]}, {r["seconds"]:.2f} s</h2><p>{r["clip"]}</p><img src="{r["number"]:02d}-{r["action"]}.png"><p>Speed {r["speed_mps"]:.2f} m/s; heading change {r["future_heading_deg"]:.1f} deg; starts: {r["past_only_start_nodes"]}</p></section>')
 (out/'index.html').write_text('\n'.join(html))
 print('FINAL '+str(out),flush=True)
if __name__=='__main__':main()
