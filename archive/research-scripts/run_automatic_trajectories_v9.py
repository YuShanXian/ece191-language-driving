"""Build trajectories to AUTOMATIC roads. Does not load human annotations."""
import json,numpy as np
from shapely.geometry import Point
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph,current_obstacles
from human_target_match import target_match
from feedback_corridors import guide_for,curve_on_guide
from trajectory_checks import motion_check,collision_check
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.multirate_tracking import track_multirate_path
out=ROOT/'runs/project-v3/automatic-road-v9';manifest=json.loads((out/'input-manifest.json').read_text());pred=json.loads((out/'predictions.json').read_text())['rows'];spec=json.loads((ROOT/'config/multirate-tracking-v1.json').read_text());controller=load_lqr_config(ROOT/spec['tracker_config']);rows=[]
for w in manifest:
 c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);run=ROOT/'runs'/w['run'];center=np.load(run/'internal_0000.npz')['center'];raw=np.load(run/'refined_v2_candidates.npz')['world_xy'];checks=json.loads((run/'ambiguity_aware_feasibility.json').read_text());saved={};obstacles,_=current_obstacles(c)
 for r in [x for x in pred if x['scene']==w['scene']]:
  target=r['selected']['target'];options=[]
  for i,p in enumerate(raw):
   p=np.vstack([center[:2],p]);m=target_match(p,float(center[6]),g,[target])
   if m['matched']:options.append({'points':p,'source':'MTR_refined','candidate':i+1,'score':checks['candidates'][i]['score'],'risk_flags':checks['candidates'][i]['rejected_by']})
  options=sorted(options,key=lambda o:(len(o['risk_flags']),-o['score']))[:6]
  if not options:
   guide=guide_for(g,r['selected']['path'],center)
   for distance in [20,30,40,50,60,80,100]:
    for duration in [6.,12.]:
     p=curve_on_guide(guide,center,distance,duration)
     if p is None or not target_match(p,float(center[6]),g,[target])['matched']:continue
     body=g.body_check(p,float(center[6]),float(center[3]),float(center[4]));motion=motion_check(p,center[7:9],initial_acceleration=checks['summary']['initial_acceleration_from_past_only']);collision=collision_check(p,float(center[6]),float(center[3]),float(center[4]),obstacles)
     flags=[k for k,v in [('road_footprint',body['passed']),('motion',motion['passed']),('constant_velocity_collision',collision['passed'])] if not v]
     options.append({'points':p,'source':'map_generated','candidate':None,'score':0.,'risk_flags':flags})
   options=sorted(options,key=lambda o:(len(o['risk_flags']),len(o['points'])))[:6]
  for o in options:
   p=o['points'];dense=np.empty((len(p)*2-1,2));dense[::2]=p;dense[1::2]=(p[:-1]+p[1:])/2;cases=[]
   for angle in [-3.,0.,3.]:
    arr,m=track_multirate_path(dense,float(center[6]),center[7:9],checks['summary']['initial_acceleration_from_past_only'],angle,controller,spec['motion_model'],control_dt=.1,integration_dt=.025)
    cases.append({'angle':angle,'points':arr['center_xy'][::4],'matched':target_match(arr['center_xy'][::4],float(center[6]),g,[target])['matched'],'maximum_error_m':m['maximum_center_error_m']})
   o['cases']=cases
  row={k:r[k] for k in ['scene','command','instruction','reason']};row['automatic_target']=target
  if options:
   pick=min(options,key=lambda o:(-sum(t['matched'] for t in o['cases']),len(o['risk_flags']),max(t['maximum_error_m'] for t in o['cases']),-o['score']));saved[f"command_{r['command']}"]=pick['points']
   for case in pick['cases']:saved[f"command_{r['command']}_track_{case['angle']:+.0f}"]=case['points']
   row.update({k:v for k,v in pick.items() if k not in ('points','cases')});row['tracking']=[{k:v for k,v in t.items() if k!='points'} for t in pick['cases']];row['status']='route_output';row['horizon_s']=(len(pick['points'])-1)/10
  else:row.update(status='no_route',source=None,tracking=[])
  rows.append(row);print(row['scene'],row['command'],row['status'],row['source'],flush=True)
 np.savez_compressed(out/f"scene-{w['scene']:02d}-selected.npz",**saved);write_json(out/'trajectory-results.json',{'rows':rows,'scope':'Automatic target-conditioned trajectory selection. No human labels read. Map supplements are not MTR predictions.'})
