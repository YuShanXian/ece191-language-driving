import json,numpy as np
from execute_language_plan_v4 import execute
from mtr_project.paths import ROOT
routes=json.loads((ROOT/'runs/project-v3/recording-demo-v1/continuous.json').read_text());p=np.array(routes['7']['path']);s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];i=np.searchsorted(s,6.3);u=(6.3-s[i-1])/(s[i]-s[i-1]);xy=p[i-1]+u*(p[i]-p[i-1]);delta=p[i]-p[i-1];state={'xy':xy.tolist(),'heading':float(np.arctan2(delta[1],delta[0])),'speed':5.6/3.6}
st={'action':'lane_change_left','source_clause':'change left lane','trigger':'now','trigger_text':'','trigger_value':None,'target_text':'','lane_reference':'relative_left','lane_number':1,'completion_text':'','constraints':[],'travel_distance_m':None,'stop_at_end':False,'target_speed_mps':None};plan={'status':'parsed','unresolved_text':[],'stages':[st]};r=execute(7,plan,state);assert np.linalg.norm(np.array(r['points'][0])-xy)<.001
print(json.dumps({'state':state,'status':r['status'],'stages':r['stages'],'follow':r.get('follow_route',{}).get('available')},indent=2));out=ROOT/'runs/project-v3/live-replanning-v6';out.mkdir(exist_ok=True);(out/'test.json').write_text(json.dumps({'state':state,'result':r},indent=2))
