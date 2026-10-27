import json,numpy as np
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph
out=ROOT/'runs/project-v3/automatic-road-v9';manifest=json.loads((out/'input-manifest.json').read_text());pred=json.loads((out/'predictions.json').read_text())['rows'];labels=json.loads((out/'evaluation-labels-snapshot.json').read_text())['reviews'];scenes={}
for w in manifest:
 s=w['scene'];run=ROOT/'runs'/w['run'];data=np.load(run/'internal_0000.npz');center=data['center'];h=center[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]]);local=lambda p:np.round((np.asarray(p)[...,:2]-center[:2])@rot,3).tolist();c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text());g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);refined=np.load(run/'refined_v2_candidates.npz')['world_xy'];selected=np.load(out/f'scene-{s:02d}-selected.npz');roads={}
 for k,n in g.nodes.items():
  xy=np.asarray(local(n.baseline.coords))
  if np.any((xy[:,0]>-40)&(xy[:,0]<160)&(xy[:,1]>-100)&(xy[:,1]<100)):roads[k]=xy.tolist()
 candidates=[{'id':i+1,'score':float(data['scores'][i]),'points':local(np.vstack([center[:2],p])),'smoothed':local(np.vstack([center[:2],refined[i]]))} for i,p in enumerate(data['world_xy'])]
 commands=[]
 for j in range(5):
  r=next(r for r in pred if r['scene']==s and r['command']==j);human=next(r for r in labels if r['scene']==s and r['command']==j)
  for k in [r['selected']['target'],*human['road_ids']]:roads[k]=local(g.nodes[k].baseline.coords)
  commands.append({'command':j,'target':r['selected']['target'],'human_roads':human['road_ids'],'output':local(selected[f'command_{j}']) if f'command_{j}' in selected else []})
 scenes[str(s)]={'candidates':candidates,'roads':roads,'commands':commands}
write_json(out/'candidate-picker-data.json',{'representation':'raw MTR world_xy, before smoothing; smoothed version available as preview overlay','scenes':scenes});print('7 scenes, 448 raw MTR candidates exported; 35 command panels')
