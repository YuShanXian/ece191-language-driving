import json,time,numpy as np
from pathlib import Path
from shapely.geometry import Point
from mtr_project.paths import ROOT
from execute_language_plan_v4 import execute
from free_navigation_v8 import context
OUT=ROOT/'runs/project-v3/common-commands-v10';OUT.mkdir(exist_ok=True)
g,initial,rot=context(7)
for ident in ['cf615973-4c9b-447f-a2b4-c182a2141fef','f9624d8f-52bf-4e5b-9ed2-387b3941e5e3']:
 raw=ROOT/'runs/project-v3/provider-benchmark-20261020/raw'/ident;p=json.loads((raw/'parsed.json').read_text());p['stages']=p['stages'][:1];state=json.loads((raw/'start-state.json').read_text());start=time.time();r=execute(7,p,state,mode='free');row=r['stages'][0];target=row.get('target');end=initial[:2]+np.asarray(r['points'][-1])@rot.T
 route=r.get('follow_route',{});length=float(np.linalg.norm(np.diff(route.get('path',[[0,0]]),axis=0),axis=1).sum());dist=float(g.nodes[target].baseline.distance(Point(end))) if target else None
 result={'case':ident,'status':r['status'],'source':row.get('trajectory_source'),'target':target,'endpoint_lane_distance':dist,'heading_change':row.get('heading_change_deg'),'onward_available':route.get('available'),'onward_m':length,'seconds':time.time()-start};result['passed']=target is not None and dist<.3 and row.get('heading_change_deg',0)>140 and route.get('available') and length>20
 (OUT/(ident+'.json')).write_text(json.dumps(r));print(json.dumps(result),flush=True)
