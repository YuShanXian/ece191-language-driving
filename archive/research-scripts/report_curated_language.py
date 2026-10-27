"""Visualize controlled-language choice coverage on seven frozen curated cases."""
import json,pickle
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('/mnt/c/Windows/Fonts/msyh.ttc')
plt.rcParams['font.family']=font_manager.FontProperties(fname='/mnt/c/Windows/Fonts/msyh.ttc').get_name()
plt.rcParams['axes.unicode_minus']=False
from matplotlib.colors import ListedColormap,BoundaryNorm
from evaluate_candidate_checks import load_graph
from audit_scene_context import metadata,forward_search,adjacent_starts
from trajectory_checks import tangent,angle_diff
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.planner import OfflinePlanner
from mtr_project.stages import Observation
from language_selector import action_matches
COMMANDS=[('Go straight','go_straight','Straight'),('Turn left','turn_left','Left turn'),('Turn right','turn_right','Right turn'),('Change lanes to the left','lane_change_left','Left lane change'),('Change lanes to the right','lane_change_right','Right lane change')]
COLORS=['#3478bf','#9052b0','#158b75','#e39726','#cf5260']
def main():
 base=ROOT/'runs/project-v3/language-choice-v1';manifest=json.loads((base/'manifest.json').read_text());assert len(manifest['windows'])==7
 report_dir=base/'report-reviewed';report_dir.mkdir(exist_ok=False);results=[];matrix=[];map_meta=None;source_hashes={str((base/'manifest.json').relative_to(ROOT)):sha256(base/'manifest.json')}
 for window in manifest['windows']:
  folder=ROOT/'samples'/window['sample'];out=ROOT/'runs'/window['run'];conv=json.loads((folder/'conversion.json').read_text());ego=pickle.load(open(folder/conv['scenario'],'rb'))['tracks']['ego']['state']
  graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map']);screen=json.loads((out/'ambiguity_aware_feasibility.json').read_text());rows=screen['candidates'];assert [r['candidate'] for r in rows]==list(range(1,65))
  for path in [out/'ambiguity_aware_feasibility.json',out/'internal_0000.npz',out/'refined_v2_candidates.npz',folder/'conversion.json',folder/conv['scenario']]:source_hashes[str(path.relative_to(ROOT))]=sha256(path)
  data=np.load(out/'internal_0000.npz');xy=np.load(out/'refined_v2_candidates.npz')['world_xy'];center=data['center'];speed=conv['current_speed_mps'];initial=float(center[6]);starts=screen['summary']['past_only_start_nodes'];final_ids={int(i)+1 for i in data['selected_indices']}
  info,edges=metadata(ROOT/conv['source_map'])
  for k,v in info.items():
   if k not in graph.nodes:continue
   b=graph.nodes[k].baseline;d=float(np.degrees(angle_diff(tangent(b,b.coords[-1]),tangent(b,b.coords[0]))));v['type']='STRAIGHT' if abs(d)<30 else ('UTURN' if abs(d)>=150 else ('LEFT' if d>0 else 'RIGHT'))
  map_options=set();near=max(30.,6*speed)
  for start in starts:
   direct=forward_search(graph,start,center[:2],info,edges,near)
   for c in direct['connectors']:
    if c['distance_to_entry_m']<=near:
     if c['turn_type']=='LEFT':map_options.add('turn_left')
     if c['turn_type']=='RIGHT':map_options.add('turn_right')
     if c['turn_type']=='STRAIGHT':map_options.add('go_straight')
   node=graph.nodes[start]
   if node.kind=='lane':
    from shapely.geometry import Point
    if node.baseline.length-node.baseline.project(Point(center[:2]))>=max(1,6*speed):map_options.add('go_straight')
    # Only immediate neighboring lane, not another lane reached after multiple changes.
    for key,relation in graph.edges.get(start,{}).items():
     if relation in ('left','right') and key in adjacent_starts(graph,start,center[:2],initial):map_options.add('lane_change_'+relation)
  choices=[];status=[];observation=Observation(window['timestamp_us']/1e6,0,0,speed)
  passing=[r for r in rows if r['passes_current_checks']];baseline=max(passing,key=lambda r:r['score'])['candidate'] if passing else None
  for text,action,label in COMMANDS:
   choice=OfflinePlanner(text).step(observation,rows);final_choice=OfflinePlanner(text).step(observation,[r for r in rows if r['candidate'] in final_ids]);matching=[r for r in rows if action_matches(r,action,speed)]
   code=2 if choice['candidate'] is not None else (1 if matching else 0);status.append(code)
   choices.append({'instruction':text,'action':action,'selected_road_route':rows[choice['candidate']-1]['route']['route'] if choice['candidate'] is not None else None,'topological_option_heuristic':action in map_options,'choice':choice,'final5_choice':final_choice,'action_matching_before_other_screens':[r['candidate'] for r in matching],'rejections':dict(Counter(reason for r in matching for reason in r['rejected_by'])),'different_from_checked_baseline':choice['candidate'] is not None and baseline is not None and choice['candidate']!=baseline})
  selected=[c for c in choices if c['choice']['candidate'] is not None]
  result={'number':window['number'],'source_window':window,'topological_options_heuristic':sorted(map_options),'passing_candidates':len(passing),'matched_routes':sum(r['route']['matched'] for r in rows),'checked_baseline_candidate':baseline,'choices':choices,'two_or_more_selectable_actions':len(selected)>=2,'distinct_selected_candidates':sorted({c['choice']['candidate'] for c in selected}),'rejections_all_candidates':dict(Counter(reason for r in rows for reason in r['rejected_by']))}
  results.append(result);matrix.append(status)
  rotation=np.array([[np.cos(initial),-np.sin(initial)],[np.sin(initial),np.cos(initial)]])
  local=lambda p:(np.asarray(p)[...,:2]-center[:2])@rotation
  fig,axes=plt.subplots(2,3,figsize=(15,9));axes=axes.ravel();actual=local(ego['position'][20:81,:2]);hist=local(ego['position'][:21,:2])
  for j,ax in enumerate(axes):
   for node in graph.nodes.values():
    p=local(node.baseline.coords);ax.plot(p[:,0],p[:,1],color='#e0e5e9',lw=.6,zorder=0)
   for p in local(xy):ax.plot(p[:,0],p[:,1],color='#95b6d5',alpha=.14,lw=.6)
   ax.plot(hist[:,0],hist[:,1],color='#222',lw=2);ax.scatter(0,0,color='#222',s=16,zorder=9)
   ax.plot(actual[:,0],actual[:,1],'--',color='#333',lw=1.4,label='Recorded future (reference)')
   if j<5:
    c=choices[j];chosen=c['choice']['candidate'];matching=c['action_matching_before_other_screens']
    if chosen is not None:
     p=local(np.vstack([center[:2],xy[chosen-1]]));ax.plot(p[:,0],p[:,1],color=COLORS[j],lw=2.8,label=f'Selected candidate {chosen}')
     subtitle='SELECTED under limited checks'
    elif matching:
     identifier=max(matching,key=lambda k:rows[k-1]['score']);p=local(np.vstack([center[:2],xy[identifier-1]]));ax.plot(p[:,0],p[:,1],color='#d88a24',lw=2,label=f'Rejected matching candidate {identifier}')
     subtitle='Matching action exists; rejected'
    else:subtitle='No road-matched action candidate'
    ax.set_title(COMMANDS[j][2]+'\n'+subtitle,fontsize=10)
   else:
    ax.set_title('All 64 derived candidates\nBlue lines are not all feasible',fontsize=10)
   # Same metric scale, fixed local view across command panels.
   ax.set_xlim(-15,80);ax.set_ylim(-45,65);ax.set_aspect('equal');ax.grid(alpha=.1);ax.set_xlabel('Forward (m)');ax.set_ylabel('Left (m)');ax.legend(fontsize=6,loc='upper right')
  fig.suptitle(f"Scene {window['number']:02d}: same observation, five commands | {len(passing)}/64 pass limited screens",fontsize=15)
  fig.text(.02,.01,'Straight is a legacy angle-threshold label, not proof of a straight road. Smoothed MTR candidates; no vehicle execution or full safety validation.',fontsize=9)
  fig.tight_layout(rect=[0,.04,1,.95]);fig.savefig(report_dir/f"scene-{window['number']:02d}.png",dpi=150);plt.close(fig)
  print(json.dumps({'scene':window['number'],'passing':len(passing),'choices':{c['action']:c['choice']['candidate'] for c in choices}}),flush=True)
 summary={'windows':7,'candidates':448,'requests':35,'selected_requests':sum(c['choice']['candidate'] is not None for r in results for c in r['choices']),'windows_with_two_selectable_actions':sum(r['two_or_more_selectable_actions'] for r in results),'by_action':{action:{'selected':sum(r['choices'][i]['choice']['candidate'] is not None for r in results),'action_matched':sum(bool(r['choices'][i]['action_matching_before_other_screens']) for r in results),'final5_selected':sum(r['choices'][i]['final5_choice']['candidate'] is not None for r in results),'topological_opportunities_heuristic':sum(r['choices'][i]['topological_option_heuristic'] for r in results),'selected_on_topological_opportunity':sum(r['choices'][i]['topological_option_heuristic'] and r['choices'][i]['choice']['candidate'] is not None for r in results)} for i,(_,action,_) in enumerate(COMMANDS)}}
 report={'summary':summary,'windows':results,'scope':'Observed sample frequencies on 7 retrospectively curated turn events from 5 logs. Not a real-world success probability; lane-change-specific sample is missing. Controlled English rules, no LLM. Derived/smoothed MTR candidates, not raw model safety.','topology_scope':'Coarse map-only opportunities: direct first geometric turn within max(30m,6*speed), or immediate adjacent lane. No legality, crossing clearance or 6s reachability guarantee.','source_sha256':source_hashes,'implementation_sha256':{p:sha256(ROOT/p) for p in ['scripts/report_curated_language.py','scripts/trajectory_checks.py','scripts/mtr_project/planner.py','scripts/mtr_project/language.py','scripts/language_selector.py']}}
 write_json(report_dir/'evaluation.json',report)
 fig,ax=plt.subplots(figsize=(11,6));cmap=ListedColormap(['#d9e0e6','#edb75f','#55ad91']);ax.imshow(matrix,cmap=cmap,norm=BoundaryNorm([-.5,.5,1.5,2.5],3),aspect='auto');ax.set_xticks(range(5),['\u672a\u8fbe\u8f6c\u5f2f\u9608\u503c*','\u5de6\u8f6c','\u53f3\u8f6c','\u5411\u5de6\u6362\u9053','\u5411\u53f3\u6362\u9053']);ax.set_yticks(range(7),[f'\u573a\u666f {r["number"]:02d}' for r in results])
 for i,r in enumerate(results):
  for j,c in enumerate(r['choices']):
   choice=c['choice']['candidate'];ax.text(j,i,f'#{choice}' if choice else ('\u88ab\u68c0\u67e5\u62d2\u7edd' if matrix[i][j]==1 else '\u65e0\u5339\u914d\u5019\u9009'),ha='center',va='center',fontsize=10)
 ax.set_title('\u540c\u4e00\u573a\u666f，\u6362\u6307\u4ee4\u540e\u80fd\u5426\u9009\u51fa\u5bf9\u5e94\u8def\u7ebf？\n\u7eff\u8272：\u901a\u8fc7\u68c0\u67e5\u5e76\u9009\u4e2d｜\u6a59\u8272：\u52a8\u4f5c\u5339\u914d\u4f46\u88ab\u62d2\u7edd｜\u7070\u8272：\u65e0\u9053\u8def\u5339\u914d\u7684\u5bf9\u5e94\u52a8\u4f5c',fontsize=13);fig.text(.02,.015,'*\u539f\u89c4\u5219\u79f0\u76f4\u884c，\u4f46\u53ef\u80fd\u6cbf\u540c\u4e00\u5f2f\u9053\u884c\u9a76。\u7eff\u8272\u4ec5\u8868\u793a\u901a\u8fc7\u6709\u9650\u68c0\u67e5，\u4e0d\u7b49\u4e8e\u8bed\u8a00\u6539\u53d8\u4e86\u9053\u8def\u65b9\u5411。',fontsize=9);fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(report_dir/'choice-matrix.png',dpi=170);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,5));selected=np.sum(np.array(matrix)==2,axis=0);rejected=np.sum(np.array(matrix)==1,axis=0);none=7-selected-rejected;x=np.arange(5)
 ax.bar(x,selected,color='#55ad91',label='\u901a\u8fc7\u68c0\u67e5\u5e76\u9009\u4e2d');ax.bar(x,rejected,bottom=selected,color='#edb75f',label='\u52a8\u4f5c\u5339\u914d\u4f46\u88ab\u62d2\u7edd');ax.bar(x,none,bottom=selected+rejected,color='#d9e0e6',label='\u65e0\u9053\u8def\u5339\u914d\u7684\u5bf9\u5e94\u52a8\u4f5c');ax.set_xticks(x,['\u672a\u8fbe\u8f6c\u5f2f\u9608\u503c*','\u5de6\u8f6c','\u53f3\u8f6c','\u5411\u5de6\u6362\u9053','\u5411\u53f3\u6362\u9053']);ax.set_ylim(0,8.5);ax.set_ylabel('\u573a\u666f\u6570（\u51717\u4e2a）');ax.set_title('\u6bcf\u79cd\u8bed\u8a00\u6307\u4ee4\u7684\u5019\u9009\u8986\u76d6\u60c5\u51b5')
 for i,n in enumerate(selected):ax.text(i,7.15,f'{n}/7 = {n/7:.0%} \u53ef\u9009',ha='center',fontsize=9)
 ax.legend(loc='upper center',bbox_to_anchor=(.5,-.1),ncol=3,fontsize=9);fig.tight_layout();fig.savefig(report_dir/'coverage.png',dpi=170);plt.close(fig)
 html=['<!doctype html><meta charset="utf-8"><title>Language choice report</title><style>body{font:17px Arial;max-width:1300px;margin:30px auto;color:#26374b}img{max-width:100%}pre{white-space:pre-wrap}</style><h1>Language choice on seven curated turn windows</h1><p>Controlled English commands select among existing derived MTR trajectories. This is offline coverage, not real driving success.</p><img src="choice-matrix.png"><img src="coverage.png">']
 for r in results:html.append(f'<h2>Scene {r["number"]:02d}</h2><img src="scene-{r["number"]:02d}.png">')
 (report_dir/'index.html').write_text('\n'.join(html));print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
