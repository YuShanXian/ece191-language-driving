import json,numpy as np
from shapely.geometry import Point
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph,current_obstacles
from human_target_match import target_match
from map_instruction_candidates import quintic
from trajectory_checks import tangent,motion_check,collision_check
from instruction_priority_selector import describe
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.multirate_tracking import track_multirate_path
out=ROOT/'runs/project-v3/human-target-v8';data=json.loads((out/'results.json').read_text());audit=json.loads((out/'selection-audit.json').read_text());spec=json.loads((ROOT/'config/multirate-tracking-v1.json').read_text());controller=load_lqr_config(ROOT/spec['tracker_config']);repair_audit=[]
for record in audit:
 if record['tracking_retained']==3:continue
 s=record['scene'];j=record['command'];w=data['windows'][s-1];ch=w['choices'][j];src=w['source_window'];run=ROOT/'runs'/src['run'];c=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);center=np.load(run/'internal_0000.npz')['center'];raw=np.load(run/'refined_v2_candidates.npz')['world_xy'];checks=json.loads((run/'ambiguity_aware_feasibility.json').read_text());wanted=ch['human_target_roads'];options=[];seen=set()
 for i,path in enumerate(raw):
  p=np.vstack([center[:2],path]);m=target_match(p,float(center[6]),g,wanted)
  if m['matched']:options.append({'p':p,'source':'MTR_refined','candidate':i+1,'mtr_score':checks['candidates'][i]['score'],'match':m})
 for key in wanted:
  n=g.nodes[key];d=n.baseline.project(Point(center[:2]))
  for extra in [5,8,12,16,20,25,30,40,50,60]:
   end=np.asarray(n.baseline.interpolate(min(d+extra,n.baseline.length-.1)).coords[0])[:2];p=quintic(center,end,tangent(n.baseline,end),checks['summary']['initial_acceleration_from_past_only']);m=target_match(p,float(center[6]),g,wanted);sig=p.tobytes()
   if m['matched'] and sig not in seen:options.append({'p':p,'source':'map_target_supplement','candidate':None,'mtr_score':None,'match':m});seen.add(sig)
 for o in options:
  p=o['p'];dense=np.empty((121,2));dense[::2]=p;dense[1::2]=(p[:-1]+p[1:])/2;o['cases']=[];o['arrays']=[]
  for angle in [-3.,0.,3.]:
   arr,m=track_multirate_path(dense,float(center[6]),center[7:9],checks['summary']['initial_acceleration_from_past_only'],angle,controller,spec['motion_model'],control_dt=.1,integration_dt=.025);match=target_match(arr['center_xy'][::4],float(center[6]),g,wanted);o['cases'].append({'initial_tire_angle_deg':angle,'target_retained':match['matched'],'target_match':match,'metrics':m});o['arrays'].append(arr)
  print('repair',s,j,o['source'],o['candidate'],'retained',sum(t['target_retained'] for t in o['cases']),flush=True)
 if not options:continue
 pick=max(options,key=lambda o:(sum(t['target_retained'] for t in o['cases']),-max(t['metrics']['maximum_center_error_m'] for t in o['cases']),o['source']=='MTR_refined'));p=pick['p'];f=describe(p,float(center[6]),{'route':{'matched':False}});f['target']={'visited_target_nodes':[pick['match']['target']]};f['human_target_match']=pick['match'];obstacles,_=current_obstacles(c)
 body=g.body_check(p,float(center[6]),float(center[3]),float(center[4]));motion=motion_check(p,center[7:9],initial_acceleration=checks['summary']['initial_acceleration_from_past_only']);coll=collision_check(p,float(center[6]),float(center[3]),float(center[4]),obstacles);flags=[k for k,v in [('road_footprint',body['passed']),('motion',motion['passed']),('constant_velocity_collision',coll['passed'])] if not v]
 ch.update(source=pick['source'],candidate=pick['candidate'],mtr_score=pick['mtr_score'],features=f,tracking={'cases':pick['cases']},risk_flags=flags,preserved_v7_route=False,horizon_s=6.)
 saved=dict(np.load(out/f'scene-{s:02d}-selected.npz'));saved[f'command_{j}']=p;np.savez_compressed(out/f'scene-{s:02d}-selected.npz',**saved)
 for angle,arr in zip([-3,0,3],pick['arrays']):np.savez_compressed(out/f'scene-{s:02d}-command-{j}-steer{angle:+d}.npz',**arr)
 record.update(tracking_retained=sum(t['target_retained'] for t in pick['cases']),source=pick['source'],candidate=pick['candidate']);repair_audit.append({'scene':s,'command':j,'options':[{'source':o['source'],'candidate':o['candidate'],'tracking_retained':sum(t['target_retained'] for t in o['cases'])} for o in options]})
write_json(out/'results.json',data);write_json(out/'selection-audit.json',audit);write_json(out/'tracking-repair-audit.json',repair_audit)
