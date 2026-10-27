"""Reverse along the traveled path; heading remains the vehicle's forward heading."""
import math
import numpy as np

def execute_reverse(scene,stage,state):
 start=np.asarray(state['xy'],float);requested=stage.get('travel_distance_m') or 10.
 if stage['action']=='reverse_continuous':requested=min(200.,sum(np.linalg.norm(np.array(b)-a) for a,b in zip(state.get('history',[])[:-1],state.get('history',[])[1:])))
 def blocked(reason):return {'scene':scene,'status':'blocked','stages':[{'action':'reverse','source_clause':stage['source_clause'],'status':'blocked','reason':reason}],'points':[start.tolist()],'speed_mps':[0.],'dt':.1}
 if not 0<requested<=200:return blocked('Reverse distance must be between 0 and 200 meters.')
 if stage.get('trigger') not in ('now','after_previous') or stage.get('constraints') or stage.get('target_text') or stage.get('completion_text'):return blocked('Reverse instruction needs unresolved conditions or destinations.')
 history=np.asarray(state.get('history',[]),float)
 if len(history)<2:return blocked('No traveled path is available for reversing. Drive forward first.')
 # The caller supplies only the already-traveled prefix, never future trajectory points.
 guide=np.vstack([start,history[::-1]]);ds=np.linalg.norm(np.diff(guide,axis=0),axis=1);guide=guide[np.r_[True,ds>1e-4]]
 if len(guide)<2:return blocked('No traveled distance is available behind the car.')
 s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(guide,axis=0),axis=1))];length=min(requested,s[-1]);n=max(20,int(math.ceil(length/1.5/.1)))
 u=np.linspace(0,1,n+1);travel=length*(3*u*u-2*u*u*u);points=np.column_stack([np.interp(travel,s,guide[:,j]) for j in range(2)])
 d=np.diff(points,axis=0);heading=np.unwrap(np.arctan2(d[:,1],d[:,0])+math.pi);heading=np.r_[heading,heading[-1]];heading[0]=state['heading']
 speed=np.r_[np.linalg.norm(d,axis=1)/.1,0.]
 row={'index':0,'action':'reverse','source_clause':stage['source_clause'],'status':'completed_offline','trajectory_source':'reverse_traveled_path','start_point':0,'end_point':n,'requested_distance_m':requested,'traveled_distance_m':float(length),'final_speed_mps':0.,'stop_at_end':True,'reason':'Backed along the already traveled path with vehicle heading preserved; stopped after reversing.'}
 return {'scene':scene,'status':'completed_offline','stages':[row],'points':points.tolist(),'speed_mps':speed.tolist(),'heading_rad':heading.tolist(),'dt':.1,'is_reverse':True,'target_speed_mps':1.5}
