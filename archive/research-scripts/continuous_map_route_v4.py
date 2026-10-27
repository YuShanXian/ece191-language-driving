import json,numpy as np
from mtr_project.paths import ROOT
from evaluate_candidate_checks import load_graph
from automatic_road_selector import select_road
from trajectory_checks import angle_diff

def cycle_path(g,start):
 seen=set();active={};trail=[]
 def dfs(k):
  if k in active:return trail.copy(),active[k]
  if k in seen:return None
  seen.add(k);active[k]=len(trail);trail.append(k)
  a=np.asarray(g.nodes[k].baseline.coords);heading=np.arctan2(*(a[-1]-a[-2])[::-1])
  nxt=[n for n,r in g.edges.get(k,{}).items() if r=='forward']
  nxt.sort(key=lambda n:abs(angle_diff(np.arctan2(*(np.asarray(g.nodes[n].baseline.coords)[1]-np.asarray(g.nodes[n].baseline.coords)[0])[::-1]),heading)))
  for n in nxt:
   out=dfs(n)
   if out:return out
  trail.pop();active.pop(k);return None
 return dfs(start)

from shapely.geometry import Point
from centerline_trajectory_planner import geometry
from scipy.interpolate import CubicSpline

def build(w):
 c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());g=load_graph(np.array(c['origin_xy_m']),c['source_epsg'],c['source_map']);center=np.load(ROOT/'runs'/w['run']/'internal_0000.npz')['center'].astype(float);r=select_road(g,center,'Go straight');found=cycle_path(g,r['current']['key'])
 if not found:return {'available':False,'reason':'No reachable directed road loop found in this map crop.'}
 path,idx=found;prefix=path[:idx];loop=path[idx:]
 if not prefix:prefix=[loop[0]];loop=loop[1:]+loop[:1]
 lp=[];gaps=[]
 for key in loop:
  line=g.nodes[key].baseline;pp=np.array([line.interpolate(d).coords[0] for d in np.r_[np.arange(0,line.length,.5),line.length]])[:,:2]
  if lp:gaps.append(float(np.linalg.norm(lp[-1]-pp[0])))
  for q in pp:
   if not lp or np.linalg.norm(q-lp[-1])>.01:lp.append(q)
 gaps.append(float(np.linalg.norm(lp[-1]-lp[0])))
 if max(gaps)>2:return {'available':False,'reason':'Map loop contains a discontinuous connection.','max_gap_m':max(gaps)}
 if np.linalg.norm(lp[-1]-lp[0])<.01:lp[-1]=lp[0]
 else:lp.append(lp[0])
 lp=np.array(lp);ss=np.r_[0,np.cumsum(np.linalg.norm(np.diff(lp,axis=0),axis=1))];curve=CubicSpline(ss,lp,bc_type='periodic');lp=curve(np.linspace(0,ss[-1],max(100,int(ss[-1]/.3))))
 shape=geometry(g,prefix+[loop[0]],center,8);initial=shape['geometry'];end=int(np.argmin(np.linalg.norm(initial-lp[0],axis=1)));initial=np.vstack([initial[:end+1],lp[0]])
 h=center[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]])
 def local(p):return np.round((np.array(p)-center[:2])@rot,4).tolist()
 return {'available':True,'entry':local(initial),'loop':local(lp),'loop_length_m':float(ss[-1]),'prefix_nodes':prefix,'loop_nodes':loop,'max_connection_gap_m':max(gaps),'roads':[local(np.array(n.baseline.coords)[:,:2]) for n in g.nodes.values()],'scope':'Continuous centerline playback on directed map connections; no traffic or vehicle-controller simulation.'}
if __name__=='__main__':
 results={}
 for w in json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text()):
  results[str(w['scene'])]=build(w);print(w['scene'],{k:v for k,v in results[str(w['scene'])].items() if k in ('available','reason','loop_length_m','max_connection_gap_m')},flush=True)
 out=ROOT/'runs/project-v3/recording-demo-v1/continuous.json';out.write_text(json.dumps(results))
