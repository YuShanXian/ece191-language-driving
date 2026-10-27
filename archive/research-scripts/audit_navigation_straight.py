import json,numpy as np
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph
from instruction_priority_v2 import forward_nodes
from trajectory_checks import tangent,angle_diff
base=ROOT/'runs/project-v3/instruction-priority-v5'
data=json.loads((base/'results.json').read_text());out=[]
for w in data['windows']:
 if w['scene'] not in (3,7):continue
 src=w['source_window'];run=ROOT/'runs'/src['run'];c=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());checks=json.loads((run/'ambiguity_aware_feasibility.json').read_text());center=np.load(run/'internal_0000.npz')['center'];g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);starts=checks['summary']['past_only_start_nodes'];nodes=set().union(*(forward_nodes(g,s,3) for s in starts))
 roads=[]
 for k in sorted(nodes):
  n=g.nodes[k];end=np.asarray(n.baseline.coords[-1])[:2];roads.append({'node':k,'kind':n.kind,'end_heading_deg':float(np.degrees(angle_diff(tangent(n.baseline,end),center[6]))),'end_distance_m':float(np.linalg.norm(end-center[:2])),'edges':g.edges.get(k,{})})
 candidates=[{'candidate':r['candidate'],'score':r['score'],'route':{k:v for k,v in r['route'].items() if k!='node_sequence'}} for r in checks['candidates'] if r['route'].get('matched') and not r['route'].get('lane_changes')]
 out.append({'scene':w['scene'],'starts':starts,'roads':roads,'candidates':candidates})
print(json.dumps(out,indent=2))

