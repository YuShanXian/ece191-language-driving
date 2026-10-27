import json,numpy as np
from shapely.geometry import Point
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph
from trajectory_checks import tangent,angle_diff
out=ROOT/'runs/project-v3/instruction-priority-v7';out.mkdir(exist_ok=True)
data=json.loads((ROOT/'runs/project-v3/instruction-priority-v6/results.json').read_text());all=[]
for w in data['windows']:
 s=w['scene'];src=w['source_window'];run=ROOT/'runs'/src['run'];conv=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());g=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);center=np.load(run/'internal_0000.npz')['center'];h=center[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]]);checks=json.loads((run/'ambiguity_aware_feasibility.json').read_text());nodes=[]
 for k,n in g.nodes.items():
  if n.baseline.distance(Point(center[:2]))>30:continue
  local=(np.asarray(n.baseline.coords)[:,:2]-center[:2])@rot;near=n.baseline.interpolate(n.baseline.project(Point(center[:2])));a=float(np.degrees(angle_diff(tangent(n.baseline,near),h)));end=float(np.degrees(angle_diff(tangent(n.baseline,n.baseline.coords[-1]),h)))
  if s in (2,4,5,7):nodes.append({'key':k,'kind':n.kind,'group':n.lane_group,'index':n.lane_index,'near':np.round((np.array(near.coords[0])[:2]-center[:2])@rot,1).tolist(),'start':np.round(local[0],1).tolist(),'end':np.round(local[-1],1).tolist(),'heading':round(a,1),'exit_heading':round(end,1),'edges':g.edges.get(k,{})})
 all.append({'scene':s,'starts':checks['summary']['past_only_start_nodes'],'nodes':nodes})
write_json(out/'map-audit.json',all)
print(json.dumps([a for a in all if a['scene']==2],ensure_ascii=False))
