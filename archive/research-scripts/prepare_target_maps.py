import json,numpy as np
from shapely.geometry import box
from mtr_project.paths import ROOT,write_json
from evaluate_candidate_checks import load_graph
base=ROOT/'runs/project-v3/instruction-priority-v7';out=base/'human-review';data=json.loads((base/'results.json').read_text());maps={}
for w in data['windows']:
 src=w['source_window'];run=ROOT/'runs'/src['run'];c=json.loads((ROOT/'samples'/src['sample']/'conversion.json').read_text());center=np.load(run/'internal_0000.npz')['center'];h=center[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]]);g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);roads=[]
 for key,n in sorted(g.nodes.items()):
  points=(np.asarray(n.baseline.coords)[:,:2]-center[:2])@rot
  from shapely.geometry import LineString
  if not LineString(points).intersects(box(-40,-80,120,100)):continue
  roads.append({'id':key,'label':'R'+str(len(roads)+1).zfill(2),'kind':n.kind,'points':np.round(points,3).tolist(),'next':g.edges.get(key,{})})
 paths=np.load(base/f'scene-{w["scene"]:02d}-selected.npz');maps[str(w['scene'])]={'roads':roads,'current':[0,0],'predictions':{k:np.round((v-center[:2])@rot,3).tolist() for k,v in paths.items()},'coordinate_system':'ego x forward metres, y left metres','version':'v7-map-1'}
write_json(out/'target-maps.json',maps)
print('Exported',sum(len(x['roads']) for x in maps.values()),'selectable map lines across 7 scenes')
