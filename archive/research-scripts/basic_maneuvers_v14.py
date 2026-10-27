import math
import numpy as np
from shapely.geometry import Point,LineString
from trajectory_checks import tangent,angle_diff

def roadside_stop(scene,stage,state,mode='free'):
 from free_navigation_v8 import context
 g,initial,rot=context(scene);start=initial[:2]+np.asarray(state['xy'])@rot.T;h=initial[6]+state['heading'];normal=np.array([-math.sin(h),math.cos(h)])
 def block(reason):return {'scene':scene,'status':'blocked','stages':[{'action':stage['action'],'status':'blocked','reason':reason}],'points':[state['xy']],'speed_mps':[state['speed']],'dt':.1}
 if stage.get('target_text') or stage.get('constraints') or stage.get('completion_text') or stage.get('trigger') not in ('now','after_previous'):return block('Needs a grounded parking destination or condition; no location was invented.')
 near=[(n.baseline.distance(Point(start)),n) for n in g.nodes.values() if n.kind=='lane' and (min(abs(angle_diff(tangent(n.baseline,start),h)),abs(math.pi-abs(angle_diff(tangent(n.baseline,start),h)))) if mode=='free' else abs(angle_diff(tangent(n.baseline,start),h)))<math.radians(40)]
 if not near or min(d for d,n in near)>8:return block('No nearby same-direction road edge. Return to a road before pulling over.')
 node=min(near,key=lambda x:x[0])[1];group=[n for d,n in near if n.lane_group==node.lane_group and d<20]
 left=stage.get('lane_reference')=='leftmost';node=sorted(group,key=lambda n:float((np.asarray(n.baseline.interpolate(n.baseline.project(Point(start))).coords[0])[:2]-start)@normal),reverse=left)[0]
 line=node.baseline
 if mode=='free' and abs(angle_diff(tangent(line,start),h))>math.pi/2:line=LineString(list(line.coords)[::-1])
 end_s=min(line.length-.2,line.project(Point(start))+15);q=np.asarray(line.interpolate(max(0,end_s)).coords[0])[:2];head=tangent(line,q);side=np.array([-math.sin(head),math.cos(head)])*(1 if left else -1)
 # Keep the vehicle center inside the road polygon, near the chosen outer edge.
 offset=0.
 for d in np.arange(.1,4,.1):
  if not node.polygon.covers(Point(q+side*(d+1.1))):break
  offset=float(d)
 end=q+side*offset;scale=max(4.,float(np.linalg.norm(end-start)));u=np.linspace(0,1,max(30,int(scale/1.5/.1)))[:,None];v0=scale*np.array([math.cos(h),math.sin(h)]);v1=scale*np.array([math.cos(head),math.sin(head)])
 z=3*u*u-2*u*u*u;pts=(2*z**3-3*z**2+1)*start+(z**3-2*z**2+z)*v0+(-2*z**3+3*z**2)*end+(z**3-z**2)*v1
 check=g.body_check(pts,h,float(initial[3]),float(initial[4]))
 if mode=='safe' and not check['passed']:return block('Road-edge stop failed conservative road-body checks.')
 speed=np.r_[np.linalg.norm(np.diff(pts,axis=0),axis=1)/.1,0.];local=(pts-initial[:2])@rot
 row={'index':0,'action':stage['action'],'source_clause':stage['source_clause'],'status':'completed_offline','start_point':0,'end_point':len(pts)-1,'target':node.key,'stop_at_end':True,'final_speed_mps':0.,'traveled_distance_m':float(np.linalg.norm(np.diff(pts,axis=0),axis=1).sum()),'reason':'Stopped near the '+('left' if left else 'right')+' road edge. This is not identification of a legal parking space.','warning':'Map-only roadside stop; parking restrictions and other vehicles are not checked.'}
 return {'scene':scene,'status':'completed_offline','stages':[row],'points':local.tolist(),'speed_mps':speed.tolist(),'dt':.1}
