"""Explicit forced-direction probes for unresolved commands, NOT road maneuvers."""
import json,numpy as np
from mtr_project.paths import ROOT,write_json
from map_instruction_candidates import quintic
from instruction_priority_selector import describe,evidence
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.multirate_tracking import track_multirate_path
from evaluate_candidate_checks import load_graph,current_obstacles
from trajectory_checks import motion_check,collision_check
base=ROOT/'runs/project-v3/instruction-priority-v3';out=ROOT/'runs/project-v3/forced-direction-probes-v1';out.mkdir(exist_ok=True)
parent=json.loads((base/'results.json').read_text());spec=json.loads((ROOT/'config/multirate-tracking-v1.json').read_text());controller=load_lqr_config(ROOT/spec['tracker_config']);results=[]
for w in parent['windows']:
 pending=[(j,ch) for j,ch in enumerate(w['choices']) if ch['status']=='no_grounded_candidate']
 if not pending:continue
 src=w['source_window'];run=ROOT/'runs'/src['run'];conv=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());screen=json.loads((run/'ambiguity_aware_feasibility.json').read_text())
 center=np.load(run/'internal_0000.npz')['center'];h=float(center[6]);rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]])
 graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);obstacles,bad=current_obstacles(conv)
 travel=np.clip(np.linalg.norm(center[7:9])*6,20,70)
 for j,ch in pending:
  action=ch['action'];endh=h
  if action.startswith('turn_'):
   sign=1 if action.endswith('left') else -1;radius=travel/(np.pi/2);endpoint=np.array([radius,sign*radius]);endh=h+sign*np.pi/2
  elif action.startswith('lane_change_'):endpoint=np.array([travel,3.5 if action.endswith('left') else -3.5])
  else:endpoint=np.array([travel,0.])
  end=center[:2]+endpoint@rot.T;points=quintic(center,end,endh,screen['summary']['initial_acceleration_from_past_only'])
  f=describe(points,h,{'route':{'matched':False}})
  if not evidence(f,action):raise ValueError('Probe does not match geometric direction')
  dense=np.empty((121,2));dense[::2]=points;dense[1::2]=(points[:-1]+points[1:])/2;cases=[]
  for angle in [-3.,0.,3.]:
   arrays,m=track_multirate_path(dense,h,center[7:9],screen['summary']['initial_acceleration_from_past_only'],angle,controller,spec['motion_model'],control_dt=.1,integration_dt=.025)
   sf=describe(arrays['center_xy'][::4],h,{'route':{'matched':False}})
   cases.append({'angle':angle,'geometric_action_retained':bool(evidence(sf,action)),'metrics':m})
   np.savez_compressed(out/f'scene-{w["scene"]:02d}-command-{j}-steer{angle:+.0f}.npz',**arrays)
  body=graph.body_check(points,h,float(center[3]),float(center[4]));motion=motion_check(points,center[7:9],initial_acceleration=screen['summary']['initial_acceleration_from_past_only']);collision=collision_check(points,h,float(center[3]),float(center[4]),obstacles)
  flags=['no_grounded_road_target','synthetic_direction_probe_not_MTR']
  flags += [k for k,v in [('road_footprint',body['passed']),('motion',motion['passed']),('constant_velocity_collision',collision['passed'])] if not v]
  np.savez_compressed(out/f'scene-{w["scene"]:02d}-command-{j}.npz',points=points)
  results.append({'scene':w['scene'],'command':j,'action':action,'source':'synthetic_direction_probe','road_action_confirmed':False,'features':f,'risk_flags':flags,'cases':cases,'checks':{'body':body,'motion':motion,'collision':collision}})
  print(w['scene'],action,sum(c['geometric_action_retained'] for c in cases),'/3',flush=True)
write_json(out/'results.json',{'results':results,'scope':'Explicit directional override probes, not successful road maneuvers. No grounded road target. Never counted as MTR candidates or road-action success.'})
