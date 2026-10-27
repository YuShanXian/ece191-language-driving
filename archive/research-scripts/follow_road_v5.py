import json,numpy as np
from mtr_project.paths import ROOT
from evaluate_candidate_checks import load_graph
from automatic_road_selector import select_road
from trajectory_checks import angle_diff,tangent

def forward_path(g,first,center,prior_groups=()):
 """Follow the local lane geometry. Route length and dead ends never affect choice."""
 from shapely.geometry import Point
 from lane_continuity_v25 import forward_choices
 entry=g.nodes[first].baseline.project(Point(center[:2]));path=[(first,entry)];used={first}
 for _ in range(400):
  current=path[-1][0]
  choices=forward_choices(g,current)
  if not choices:break
  # Choose locally before checking visited nodes: never choose a different
  # road merely to lengthen the route or avoid a dead end / repeated road.
  nxt=choices[0]
  if nxt in used:break
  used.add(nxt);path.append((nxt,0.))
 points=[center[:2].copy()]
 for key,start in path:
  line=g.nodes[key].baseline
  points.extend(np.asarray(line.interpolate(float(v)).coords[0])[:2] for v in np.r_[np.arange(start+.4,line.length,.4),line.length])
 line=g.nodes[first].baseline;offset=center[:2]-np.asarray(line.interpolate(entry).coords[0])[:2];distance=0.
 for i in range(1,len(points)):
  distance+=float(np.linalg.norm(points[i]-points[i-1]))
  if distance>=8:break
  points[i]=points[i]+offset*(1-distance/8)**2
 points=np.asarray(points);points=points[np.r_[True,np.linalg.norm(np.diff(points,axis=0),axis=1)>.001]]
 return [x[0] for x in path],'Current lane route ends; reverse along the traveled path or request another maneuver',points

def build(w,initial_state=None):
 c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());g=load_graph(np.array(c['origin_xy_m']),c['source_epsg'],c['source_map']);center=np.load(ROOT/'runs'/w['run']/'internal_0000.npz')['center'].astype(float)
 initial=center.copy()
 if initial_state is not None:
  h=initial[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]]);center[:2]=initial[:2]+np.array(initial_state['xy'])@rot.T;center[6]=initial[6]+initial_state['heading']
 r=select_road(g,center,'Go straight')
 preferred=(initial_state or {}).get('lane_key')
 if preferred in g.nodes and (initial_state or {}).get('lane_reversed'):
  from shapely.geometry import LineString,Point
  key=preferred;seen=set();points=[center[:2].copy()]
  for _ in range(200):
   seen.add(key);line=LineString(list(g.nodes[key].baseline.coords)[::-1]);start=line.project(Point(points[-1])) if len(seen)==1 else 0.
   points.extend(np.array(line.interpolate(float(s)).coords[0])[:2] for s in np.r_[np.arange(start+.5,line.length,.5),line.length])
   nxt=[k for k,edges in g.edges.items() if edges.get(key)=='forward' and k not in seen]
   if not nxt:break
   head=tangent(line,points[-1]);key=min(nxt,key=lambda k:abs(angle_diff(tangent(g.nodes[k].baseline,points[-1])+np.pi,head)))
  h=initial[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]])
  def local(p):return np.round((np.array(p)-initial[:2])@rot,4).tolist()
  return {'available':len(points)>2,'start_speed_mps':initial_state.get('speed',0),'path':local(points),'nodes':list(seen),'end_reason':'End of reverse-direction map connections','roads':[local(np.array(n.baseline.coords)[:,:2]) for n in g.nodes.values() if not n.key.startswith('J_')]}
 if preferred in g.nodes:
  from shapely.geometry import Point
  n=g.nodes[preferred]
  if n.baseline.distance(Point(center[:2]))<1 and abs(angle_diff(tangent(n.baseline,center[:2]),center[6]))<np.radians(30):r={'current':{'key':preferred}}
 if 'current' not in r:
  from shapely.geometry import Point
  nearby=[]
  for n in g.nodes.values():
   d=n.baseline.distance(Point(center[:2]));a=abs(angle_diff(tangent(n.baseline,center[:2]),center[6]))
   if d<4 and a<np.radians(75):nearby.append((d+2*a,n.key))
  if nearby:r={'current':{'key':min(nearby)[1]}}
 if 'current' not in r:return {'available':False,'reason':'No current map lane found.'}
 keys,reason,points=forward_path(g,r['current']['key'],center)
 if len(points)<2:return {'available':False,'reason':'At the end of connected map roads'}
 h=initial[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]])
 def local(p):return np.round((np.array(p)-initial[:2])@rot,4).tolist()
 return {'available':True,'start_speed_mps':float(initial_state.get('speed',0)) if initial_state else 0.,'path':local(points),'nodes':keys,'end_reason':reason,'roads':[local(np.array(n.baseline.coords)[:,:2]) for n in g.nodes.values() if not n.key.startswith('J_')],'scope':'Keep the landing lane and follow forward connections. Never add a lateral lane change without an explicit instruction. Stop before map path end. No automatic U-turn or lap replay.'}
if __name__=='__main__':
 result={}
 for w in json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text()):
  r=build(w);result[str(w['scene'])]=r;print(w['scene'],r['available'],len(r.get('nodes',[])),flush=True)
 (ROOT/'runs/project-v3/recording-demo-v1/continuous.json').write_text(json.dumps(result))
