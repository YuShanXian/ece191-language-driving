import json,hashlib,numpy as np
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph,current_obstacles
from feedback_corridors import guide_for,curve_on_guide,corridor_evidence
from trajectory_checks import motion_check,collision_check
from instruction_priority_selector import describe
from mtr_project.tracking_diagnostic import load_lqr_config
from mtr_project.multirate_tracking import track_multirate_path
base=ROOT/'runs/project-v3/instruction-priority-v6';out=ROOT/'runs/project-v3/instruction-priority-v7';out.mkdir(exist_ok=True)
# Target interpretations from round-3 human feedback plus inspected map; NOT a held-out test.
specs=[{'scene':1,'command':3,'mode':'continue','reason':'\u4f60\u8981\u6c42：\u6ca1\u6709\u66f4\u5de6\u7684\u76f4\u884c\u8f66\u9053\u65f6，\u7ee7\u7eed\u76f4\u884c。'}, {'scene':2,'command':3,'mode':'corridor','keys':['L68552','C69915','L67124'],'minimum_progress':18,'distances':[24,28,32,36,40],'reason':'\u5148\u8fdb\u5165\u5de6\u4fa7\u8f66\u9053，\u518d\u6cbf\u8be5\u8f66\u9053\u7684\u9053\u8def\u8fde\u63a5\u8d70，\u907f\u514d\u9009\u4e2d\u8fd4\u56de\u539f\u8f66\u9053\u7684\u4ea4\u53c9\u7ebf。'}, {'scene':2,'command':4,'mode':'corridor','keys':['L68569','C69133','L67133'],'minimum_progress':10,'distances':[12,16,20,24,28],'reason':'\u53f3\u4fa7\u9053\u8def\u5b58\u5728，\u4f46\u5c5e\u4e8e\u4e0d\u540c\u5730\u56fe\u5206\u7ec4，\u65e7\u7a0b\u5e8f\u53ea\u5728\u540c\u7ec4\u67e5\u627e\u800c\u6f0f\u6389。'}, {'scene':4,'command':1,'mode':'refuse','reason':'\u9644\u8fd1\u8fde\u63a5\u9053\u8def\u6ca1\u6709\u627e\u5230\u53ef\u8fbe\u7684\u5de6\u8f6c\u51fa\u53e3，\u64a4\u56de\u539f\u6765\u671d\u969c\u788d\u7269\u65b9\u5411\u7684\u8def\u7ebf。'}, {'scene':5,'command':2,'mode':'corridor','keys':['L67711','C69010','L67827','C69143','L67774'],'minimum_progress':68,'distances':[72,74,76],'duration':12,'reason':'\u7ecf\u53f3\u4fa7\u8f66\u9053\u524d\u5f80\u53f3\u8f6c\u51fa\u53e3，\u7981\u6b62\u5148\u7ed5\u5230\u5de6\u4fa7\u5bf9\u5411\u9053\u8def。'}, {'scene':5,'command':3,'mode':'continue','reason':'\u6ca1\u6709\u540c\u5411\u5de6\u8f66\u9053，\u4fdd\u7559\u76f4\u884c\u8def\u7ebf，\u4e0d\u8fdb\u5165\u5bf9\u5411\u8f66\u9053。'}, {'scene':6,'command':3,'mode':'continue','reason':'\u6309\u4f60\u7684\u9053\u8def\u89e3\u91ca，\u5df2\u7ecf\u5728\u6700\u5de6\u4fa7\u76f4\u884c\u4f4d\u7f6e，\u7ee7\u7eed\u76f4\u884c。'}, {'scene':7,'command':1,'mode':'corridor','keys':['L63424','C70086','L67707'],'minimum_progress':27,'distances':[28,32,36,40,44],'reason':'\u9009\u62e9\u771f\u6b63\u7684\u5de6\u8f6c\u51fa\u53e3，\u4e0d\u518d\u628a\u524d\u65b9\u9053\u8def\u7684\u5c0f\u5e45\u5f2f\u66f2\u5f53\u5de6\u8f6c。'}, {'scene':7,'command':4,'mode':'continue','reason':'\u6700\u53f3\u8f66\u9053\u6ca1\u6709\u53f3\u4fa7\u540c\u5411\u8f66\u9053，\u663e\u793a\u7ee7\u7eed\u884c\u9a76\u8def\u7ebf。'}]
write_json(out/'repair-specifications.json',{'source':'Human round-3 reviews and inspected map. Explicit development-scene interpretations; not autonomous generalization.','repairs':specs})
data=json.loads((base/'results.json').read_text());tracking_spec=json.loads((ROOT/'config/multirate-tracking-v1.json').read_text());controller=load_lqr_config(ROOT/tracking_spec['tracker_config']);audit=[]
for w in data['windows']:
 s=w['scene'];saved=dict(np.load(base/f'scene-{s:02d}-selected.npz'));repairs=[r for r in specs if r['scene']==s]
 src=w['source_window'];run=ROOT/'runs'/src['run'];conv=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());checks=json.loads((run/'ambiguity_aware_feasibility.json').read_text());center=np.load(run/'internal_0000.npz')['center'];xy=np.load(run/'refined_v2_candidates.npz')['world_xy'];g=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);obstacles,_=current_obstacles(conv)
 for repair in repairs:
  j=repair['command'];old=w['choices'][j];ch=dict(old);ch['repair']=repair;ch['human_confirmed']=False
  if repair['mode']=='continue':
   straight=w['choices'][0];ch={**straight,'action':old['action'],'instruction':old['instruction'],'old_candidate':old.get('old_candidate'),'repair':repair,'effective_action':'continue_without_requested_lane_change','human_confirmed':False};saved[f'command_{j}']=saved['command_0'].copy();ch['tracking_reference']={'version':'instruction-priority-v6','scene':s,'command':0}
  elif repair['mode']=='refuse':
   saved.pop(f'command_{j}',None);ch.update(status='refused_no_reachable_road',source=None,effective_action='no_requested_maneuver',risk_flags=[],tracking=None)
  else:
   guide=guide_for(g,repair['keys'],center);options=[]
   for row,path in zip(checks['candidates'],xy):
    p=np.vstack([center[:2],path]);ev=corridor_evidence(p,center,guide,ch['action'],repair['minimum_progress'])
    if ev:options.append({'points':p,'source':'MTR_refined','candidate':row['candidate'],'mtr_score':row['score'],'evidence':ev})
   for dist in repair['distances']:
    p=curve_on_guide(guide,center,dist,repair.get('duration',6))
    if p is None:continue
    ev=corridor_evidence(p,center,guide,ch['action'],repair['minimum_progress'])
    if ev:options.append({'points':p,'source':'map_corridor_supplement','candidate':None,'mtr_score':None,'evidence':ev})
   for o in options:
    p=o['points'];dense=np.empty((2*len(p)-1,2));dense[::2]=p;dense[1::2]=(p[:-1]+p[1:])/2;o['cases']=[];o['arrays']=[]
    for angle in [-3.,0.,3.]:
     arrays,m=track_multirate_path(dense,float(center[6]),center[7:9],checks['summary']['initial_acceleration_from_past_only'],angle,controller,tracking_spec['motion_model'],control_dt=.1,integration_dt=.025)
     ev=corridor_evidence(arrays['center_xy'][::4],center,guide,ch['action'],repair['minimum_progress']);o['cases'].append({'initial_tire_angle_deg':angle,'target_retained':ev is not None,'metrics':m});o['arrays'].append(arrays)
   if options:
    pick=max(options,key=lambda o:(sum(x['target_retained'] for x in o['cases']),-o['evidence']['end_centerline_distance_m'],-max(x['metrics']['maximum_center_error_m'] for x in o['cases']),o['source']=='MTR_refined'))
    p=pick['points'];ch['horizon_s']=(len(p)-1)/10;body=g.body_check(p,float(center[6]),float(center[3]),float(center[4]));motion=motion_check(p,center[7:9],initial_acceleration=checks['summary']['initial_acceleration_from_past_only']);collision=collision_check(p,float(center[6]),float(center[3]),float(center[4]),obstacles)
    f=describe(p,float(center[6]),{'route':{'matched':False}});f['target']={'visited_target_nodes':repair['keys']};f['corridor_evidence']=pick['evidence'];ch.update(status='destination_grounded_offline',source=pick['source'],candidate=pick['candidate'],mtr_score=pick['mtr_score'],features=f,tracking={'cases':pick['cases']},risk_flags=[k for k,v in [('road_footprint',body['passed']),('motion',motion['passed']),('constant_velocity_collision',collision['passed'])] if not v],checks={'body':body,'motion':motion,'collision':collision});saved[f'command_{j}']=p
    for angle,arrays in zip([-3,0,3],pick['arrays']):np.savez_compressed(out/f'scene-{s:02d}-command-{j}-steer{angle:+d}.npz',**arrays)
   else:ch.update(status='repair_unresolved',source=None,tracking=None,repair_problem='No trajectory satisfies target corridor; old rejected route removed');saved.pop(f'command_{j}',None)
   audit.append({'scene':s,'command':j,'guide_length_m':guide.length,'alternatives':[{'source':o['source'],'candidate':o['candidate'],'evidence':o['evidence'],'retained':sum(x['target_retained'] for x in o['cases'])} for o in options]})
  w['choices'][j]=ch;print(s,j,ch['status'],ch.get('source'),sum(c['target_retained'] for c in (ch.get('tracking') or {}).get('cases',[])),flush=True)
 np.savez_compressed(out/f'scene-{s:02d}-selected.npz',**saved)
data['scope']='Development-only repairs explicitly informed by round-3 human feedback and local map. New human assessment pending; no retraining.'
write_json(out/'results.json',data);write_json(out/'repair-audit.json',audit)
review=base/'human-review/reviews.json';write_json(out/'prior-human-review-summary.json',{'sha256':hashlib.sha256(review.read_bytes()).hexdigest(),'success':27,'fail':7,'uncertain':1,'total':35,'human_success_over_all':27/35})


