import json,numpy as np,hashlib
from shapely.geometry import Point
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph,current_obstacles
from human_target_match import target_match
from trajectory_checks import tangent,motion_check,collision_check
from map_instruction_candidates import quintic
from instruction_priority_selector import describe
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.multirate_tracking import track_multirate_path
base=ROOT/'runs/project-v3/instruction-priority-v7';out=ROOT/'runs/project-v3/human-target-v8';data=json.loads((base/'results.json').read_text());targets=json.loads((out/'human-targets-snapshot.json').read_text());before=json.loads((out/'comparison-before.json').read_text())['rows'];spec=json.loads((ROOT/'config/multirate-tracking-v1.json').read_text());controller=load_lqr_config(ROOT/spec['tracker_config']);audit=[]
for w in data['windows']:
 s=w['scene'];src=w['source_window'];run=ROOT/'runs'/src['run'];c=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);center=np.load(run/'internal_0000.npz')['center'];paths=np.load(base/f'scene-{s:02d}-selected.npz');raw=np.load(run/'refined_v2_candidates.npz')['world_xy'];checks=json.loads((run/'ambiguity_aware_feasibility.json').read_text());rows=checks['candidates'];obstacles,_=current_obstacles(c);cache={};saved={}
 def track(p):
  key=hashlib.sha256(p.tobytes()).hexdigest()
  if key not in cache:
   dense=np.empty((2*len(p)-1,2));dense[::2]=p;dense[1::2]=(p[:-1]+p[1:])/2;cache[key]=[]
   for angle in [-3.,0.,3.]:
    arr,m=track_multirate_path(dense,float(center[6]),center[7:9],checks['summary']['initial_acceleration_from_past_only'],angle,controller,spec['motion_model'],control_dt=.1,integration_dt=.025);cache[key].append((arr,m,angle))
  return cache[key]
 for j,old in enumerate(w['choices']):
  wanted=targets['reviews'][(s-1)*5+j]['road_ids'];b=before[(s-1)*5+j];options=[]
  if b['before_status']=='matches_selected_road':
   p=paths[f'command_{j}'];options.append({'points':p,'source':old['source'],'candidate':old.get('candidate'),'mtr_score':old.get('mtr_score'),'preserved':True})
  else:
   candidate_ids=sorted(b['alternative_mtr_candidates'],key=lambda k:rows[k-1]['score'],reverse=True)[:6]
   for k in candidate_ids:options.append({'points':np.vstack([center[:2],raw[k-1]]),'source':'MTR_refined','candidate':k,'mtr_score':rows[k-1]['score'],'preserved':False})
  if not options:
   for key in wanted:
    n=g.nodes[key];d=n.baseline.project(Point(center[:2]))
    for extra in [5,10,15,20,30,40]:
     end=np.asarray(n.baseline.interpolate(min(d+extra,n.baseline.length-.1)).coords[0])[:2]
     p=quintic(center,end,tangent(n.baseline,end),checks['summary']['initial_acceleration_from_past_only'])
     m=target_match(p,float(center[6]),g,wanted)
     if m['matched']:options.append({'points':p,'source':'map_target_supplement','candidate':None,'mtr_score':None,'preserved':False})
  for o in options:
   o['match']=target_match(o['points'],float(center[6]),g,wanted);o['cases']=[]
   for arr,m,angle in track(o['points']):
    match=target_match(arr['center_xy'][::4],float(center[6]),g,wanted)
    o['cases'].append({'initial_tire_angle_deg':angle,'target_retained':match['matched'],'target_match':match,'metrics':m})
  ch=dict(old);ch.update(human_target_roads=wanted,human_target_conditioned=True,human_confirmed=False,previous_v7_status=old['status']);ch.pop('tracking_reference',None);ch.pop('repair',None)
  if options:
   def rank(o):
    return (sum(x['target_retained'] for x in o['cases']),-max(x['metrics']['maximum_center_error_m'] for x in o['cases']),o.get('mtr_score') or 0.)
   pick=max(options,key=rank);p=pick['points'];f=describe(p,float(center[6]),{'route':{'matched':False}});f['target']={'visited_target_nodes':[pick['match']['target']]};f['human_target_match']=pick['match']
   if pick['preserved']:flags=old.get('risk_flags',[])
   elif pick['source']=='MTR_refined':flags=rows[pick['candidate']-1]['rejected_by']
   else:
    body=g.body_check(p,float(center[6]),float(center[3]),float(center[4]));motion=motion_check(p,center[7:9],initial_acceleration=checks['summary']['initial_acceleration_from_past_only']);coll=collision_check(p,float(center[6]),float(center[3]),float(center[4]),obstacles);flags=[k for k,v in [('road_footprint',body['passed']),('motion',motion['passed']),('constant_velocity_collision',coll['passed'])] if not v]
   ch.update(status='destination_grounded_offline',source=pick['source'],candidate=pick['candidate'],mtr_score=pick['mtr_score'],features=f,tracking={'cases':pick['cases']},risk_flags=flags,horizon_s=(len(p)-1)/10,preserved_v7_route=pick['preserved']);saved[f'command_{j}']=p
   for arr,m,angle in track(p):np.savez_compressed(out/f'scene-{s:02d}-command-{j}-steer{angle:+.0f}.npz',**arr)
   verdict=sum(x['target_retained'] for x in pick['cases'])
  else:ch.update(status='human_target_unresolved',source=None,tracking=None);verdict=0
  w['choices'][j]=ch;audit.append({'scene':s,'command':j,'before_status':b['before_status'],'after_has_route':bool(options),'tracking_retained':verdict,'alternatives_tested':len(options),'source':ch.get('source'),'candidate':ch.get('candidate'),'human_targets':wanted})
  print(s,j,ch['status'],ch.get('source'),'retained',verdict,flush=True)
 np.savez_compressed(out/f'scene-{s:02d}-selected.npz',**saved)
 write_json(out/'results.json',{**data,'scope':'Human target-conditioned development experiment. User feasible roads are selection inputs, NOT held-out labels. Not autonomous language accuracy. MTR weights unchanged.'});write_json(out/'selection-audit.json',audit)
