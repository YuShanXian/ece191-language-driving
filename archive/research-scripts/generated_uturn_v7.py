"""Generate a U-turn even without a pre-labelled map connection; report map fit separately."""
import numpy as np
from shapely.geometry import Point
from centerline_trajectory_planner import geometry,CONFIG
from distance_motion_v3 import distance_motion
from trajectory_checks import tangent,angle_diff

def generate(graph,center,acc,free=False):
 if free:
  from uturn_return_v10 import generate_to_lane
  result=generate_to_lane(graph,center,acc)
  if result is not None:return result
 config=dict(CONFIG);config['cruise_speed_mps']=4.
 candidates=[];pos=Point(center[:2]);v0=float(np.linalg.norm(center[7:9]))
 targets=[n for n in graph.nodes.values() if n.kind=='lane' and n.baseline.distance(pos)<60 and abs(angle_diff(tangent(n.baseline,center[:2]),center[6]))>np.radians(150)]
 targets.sort(key=lambda n:n.baseline.distance(pos))
 for node in targets[:12]:
  for join in (12.,18.,25.,35.,50.):
   try:
    shape=geometry(graph,[node.key],center,join);distance=min(shape['length']-max(4.,center[3]/2+1.5),join+12)
    if distance<5:continue
    end=shape['curve'](distance);der=shape['curve'](distance,1)
    if abs(angle_diff(np.arctan2(der[1],der[0]),center[6]))<np.radians(150) or node.baseline.distance(Point(end))>1:continue
    steer=float(np.max(np.abs(np.arctan(CONFIG['wheelbase_m']*shape['curvature']))))
    if steer>CONFIG['steering_limit_rad']:continue
    candidates.append((shape,distance,node.key,'generated_to_opposite_lane',steer))
   except (ValueError,IndexError):continue
 # A constant-radius half circle is an explicit geometric fallback, not a map connection.
 radius=max(6.,v0*v0/1.8)
 for sign in (1.,-1.):
  h=float(center[6]);start=center[:2].copy();length=np.pi*radius
  def curve(s,nu=0,sign=sign,h=h,start=start,radius=radius):
   a=h+sign*np.asarray(s)/radius
   if nu==1:return np.stack([np.cos(a),np.sin(a)],axis=-1)
   return start+np.stack([sign*radius*(np.sin(a)-np.sin(h)),sign*radius*(-np.cos(a)+np.cos(h))],axis=-1)
  arc=np.arange(0,length+1,.2);shape={'curve':curve,'length':length+1.01,'arc_s':arc,'curvature':np.full(len(arc),sign/radius)}
  candidates.append((shape,length,None,'generated_geometric_uturn',float(np.arctan(CONFIG['wheelbase_m']/radius))))
 options=[]
 for shape,distance,target,source,steer in candidates:
  try:p,timing=distance_motion(shape,center,acc,distance,True,config)
  except ValueError:continue
  body=graph.body_check(p,float(center[6]),float(center[3]),float(center[4]))
  options.append((not body['passed'],target is None,len(body['outside_sample_steps']),distance,p,timing,target,source,steer,body))
 if not options:raise ValueError('Could not generate a U-turn from the current speed.')
 chosen=min(options,key=lambda x:x[:4]);_,_,_,distance,p,timing,target,source,steer,body=chosen
 d=p[-1]-p[max(0,len(p)-5)];heading=float(np.arctan2(d[1],d[0]));change=abs(float(angle_diff(heading,center[6])))
 info={'trajectory_source':source,'target':target,'body_check_passed':body['passed'],'max_steering_rad':steer,'heading_change_deg':float(np.degrees(change)),'road_fit':'inside mapped road' if body['passed'] else 'leaves mapped road','reason':('Program-generated U-turn; '+('ends in an opposite-facing map lane. ' if target else 'no mapped destination lane. ')+('Road footprint check passed; traffic and legality are not checked.' if body['passed'] else 'WARNING: trajectory leaves the mapped road; geometry demonstration only.'))}
 return p,timing,heading,info
