import json,numpy as np
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph,current_obstacles
from centerline_trajectory_planner import CONFIG,geometry,time_parameterize,path_metrics
from human_target_match import target_match
from trajectory_checks import collision_check
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.multirate_tracking import track_multirate_path
base=ROOT/'runs/project-v3/automatic-road-v9';out=ROOT/'runs/project-v3/centerline-planner-v1';out.mkdir(exist_ok=True);manifest=json.loads((base/'input-manifest.json').read_text());pred=json.loads((base/'predictions.json').read_text())['rows'];spec=json.loads((ROOT/'config/multirate-tracking-v1.json').read_text());controller=load_lqr_config(ROOT/spec['tracker_config']);write_json(out/'config.json',CONFIG);rows=[]
for w in manifest:
 s=w['scene'];c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);run=ROOT/'runs'/w['run'];center=np.load(run/'internal_0000.npz')['center'];acc=json.loads((run/'ambiguity_aware_feasibility.json').read_text())['summary']['initial_acceleration_from_past_only'];obstacles,_=current_obstacles(c);saved={};cache={}
 for r in [r for r in pred if r['scene']==s]:
  j=r['command'];keys=r['selected']['path'];key=tuple(keys)
  if key not in cache:
   options=[]
   for join in CONFIG['join_distances_m']:
    shape=geometry(g,keys,center,join);p,timing=time_parameterize(shape,center,acc);body=g.body_check(p,float(center[6]),float(center[3]),float(center[4]));match=target_match(p,float(center[6]),g,[r['selected']['target']]);metrics=path_metrics(p,shape['guide'],center[7:9],acc);steer=float(np.max(np.abs(np.arctan(CONFIG['wheelbase_m']*shape['curvature']))))
    options.append({'shape':shape,'points':p,'timing':timing,'body':body,'target_match':match,'metrics':metrics,'steering_rad':steer})
   # Fixed geometry/dynamics ranking, not human answers or model scores.
   def rank(o):return (o['steering_rad']>CONFIG['steering_limit_rad'],len(o['body']['outside_sample_steps']),o['timing']['initial_speed_above_braking_envelope'],o['timing']['peak_lateral_accel_mps2']>3.,not o['target_match']['matched'],o['metrics']['motion']['peaks']['jerk_mps3'],o['metrics']['mean_centerline_distance_m'])
   pick=min(options,key=rank);p=pick['points'];dense=np.empty((2*len(p)-1,2));dense[::2]=p;dense[1::2]=(p[:-1]+p[1:])/2;tracks=[]
   for angle in [-3.,0.,3.]:
    arr,m=track_multirate_path(dense,float(center[6]),center[7:9],acc,angle,controller,spec['motion_model'],control_dt=.1,integration_dt=.025);tracks.append({'angle':angle,'points':arr['center_xy'][::4],'metrics':m})
   pick['tracks']=tracks;cache[key]=pick
  pick=cache[key];p=pick['points'];saved[f'command_{j}']=p;saved[f'guide_{j}']=np.asarray(pick['shape']['guide'].coords);saved[f'speed_{j}']=np.asarray(pick['timing']['speed_mps']);saved[f'progress_{j}']=np.asarray(pick['timing']['progress_m']);trackrows=[]
  for case in pick['tracks']:
   saved[f"command_{j}_track_{case['angle']:+.0f}"]=case['points'];trackrows.append({'initial_steer_deg':case['angle'],'target_match':target_match(case['points'],float(center[6]),g,[r['selected']['target']])['matched'],'metrics':case['metrics']})
  coll=collision_check(p,float(center[6]),float(center[3]),float(center[4]),obstacles);row={'scene':s,'command':j,'instruction':r['instruction'],'target':r['selected']['target'],'path':keys,'source':'deterministic_map_centerline','join_distance_m':pick['shape']['join_m'],'horizon_s':CONFIG['horizon_s'],'metrics':pick['metrics'],'timing':pick['timing'],'body':pick['body'],'collision':coll,'target_match':pick['target_match'],'steering_rad':pick['steering_rad'],'tracking':trackrows}
  rows.append(row);print(s,j,'target',row['target_match']['matched'],'body',row['body']['passed'],'motion',row['metrics']['motion']['passed'],'track',sum(t['target_match'] for t in trackrows),flush=True)
 np.savez_compressed(out/f'scene-{s:02d}-selected.npz',**saved);write_json(out/'results.json',{'rows':rows,'scope':'Deterministic map-centerline planner using fixed v9 automatic road decisions. No MTR predictions used in generation. 12-second offline plans, not 12-second forecasts. Collision checks do not perform avoidance.'})
