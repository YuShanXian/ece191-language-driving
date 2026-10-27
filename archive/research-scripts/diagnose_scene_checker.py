import json,pickle,numpy as np
from datetime import datetime,timezone
from shapely.geometry import Point,LineString
from evaluate_candidate_checks import load_graph
from mtr_project.connector_routes import add_parallel_connector_edges
from trajectory_checks import headings,angle_diff,tangent,footprint
from mtr_project.paths import ROOT,write_json
out=ROOT/'runs/project-v3/checker-diagnosis'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');out.mkdir(parents=True)
a=json.loads((ROOT/'runs/project-v3/scene-context/20261019T072018Z/audit.json').read_text());rows=[]
for row in a['windows']:
 if row['recorded_future_match']['matched'] and row['recorded_future_body_check']['passed']:continue
 c=json.loads((ROOT/'samples'/row['window']['sample']/'conversion.json').read_text())
 e=pickle.load(open(ROOT/'samples'/row['window']['sample']/c['scenario'],'rb'))['tracks']['ego']['state']
 g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map'])
 xy=e['position'][20:81,:2];h=e['heading'][20:81];inferred=headings(xy,h[0]);length=float(e['length'][20]);width=float(e['width'][20])
 body=[]
 for i in range(61):
  p=footprint(xy[i],h[i],length,width);q=footprint(xy[i],inferred[i],length,width)
  if not g.surface.covers(p) or not g.surface.covers(q):body.append({'step':i,'heading_error_deg':float(np.degrees(angle_diff(inferred[i],h[i]))),'recorded_heading_outside_area_m2':p.difference(g.surface).area,'inferred_heading_outside_area_m2':q.difference(g.surface).area})
 patched, added=add_parallel_connector_edges(g)
 history=g.match(e['position'][:21,:2],float(e['heading'][0]),return_end_states=True)
 starts={r['node'] for r in history.get('viable_end_states',[])}
 detail={'key':row['key'],'body':body,'past_only_viable_start_nodes':sorted(starts),'ambiguity_aware_match':g.match(xy,h[0],start_nodes=starts),'parallel_connector_hypothesis_match':patched.match(xy,h[0],start_nodes={row['current_node']}),'added_parallel_edges':added}
 if not row['recorded_future_match']['matched']:
  i=row['recorded_future_match']['failure_step'];before=g.match(xy[:i],h[0],start_nodes={row['current_node']});detail['prefix']=before
  prior=before['node_sequence'][-1];detail['failure_candidates']=[]
  for idx in g.tree.query(Point(xy[i]),predicate='intersects'):
   key=g.keys[int(idx)];n=g.nodes[key];paths=g.paths(prior,key)
   detail['failure_candidates'].append({'node':key,'prior':prior,'angle_error_deg':float(np.degrees(angle_diff(inferred[i],tangent(n.baseline,xy[i])))),'paths':[{'nodes':list(p),'uncovered_segment_m':LineString(xy[i-1:i+1]).difference(g.corridor(p)).length} for p in paths]})
 rows.append(detail);print(json.dumps({k:v for k,v in detail.items() if k not in ('added_parallel_edges','prefix')}),flush=True)
write_json(out/'diagnosis.json',rows);print(out)
