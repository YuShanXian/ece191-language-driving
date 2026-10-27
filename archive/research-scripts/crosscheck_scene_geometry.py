import json, sqlite3, numpy as np
from pathlib import Path
from audit_scene_context import ROOT, load_graph, tangent, angle_diff
from nuplan.common.maps.maps_datatypes import LaneConnectorType
from PIL import Image, ImageOps, ImageDraw
folder=ROOT/'runs/project-v3/scene-context/20261019T071757Z'
a=json.loads((folder/'audit.json').read_text())
print('ENUM', list(LaneConnectorType))
rows=[]
for r in a['windows']:
 c=json.loads((ROOT/'samples'/r['window']['sample']/'conversion.json').read_text())
 g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map'])
 if not rows:
  con=sqlite3.connect(str(ROOT/c['source_map']))
  print('TYPE TABLES',con.execute("select name from sqlite_master where type='table' and name like '%turn%'").fetchall())
  for (name,) in con.execute("select name from sqlite_master where type='table' and name like '%turn%'").fetchall():print(name,con.execute('select * from '+name).fetchmany(20))
 turns=[]
 for source,s in [('direct',r['direct'])]+[('adjacent',v['search']) for v in r['adjacent']]:
  for v in s['connectors']:
   n=g.nodes[v['connector']];b=n.baseline
   change=float(np.degrees(angle_diff(tangent(b,b.coords[-1]),tangent(b,b.coords[0]))))
   turns.append(dict(v,source=source,geometry_change_deg=change))
 rows.append({'key':r['key'],'connectors':turns})
 print(r['key'],[(v['connector'],v['turn_type'],round(v['geometry_change_deg'],1)) for v in turns if v['source']=='direct'])
(folder/'geometry-crosscheck.json').write_text(json.dumps(rows,indent=2))
for start in (0,7):
 subset=a['windows'][start:start+7];canvas=Image.new('RGB',(1350,1050),'white')
 for i,r in enumerate(subset):
  im=Image.open(folder/(r['key']+'.png'));im.thumbnail((450,350));canvas.paste(im,((i%3)*450,(i//3)*350))
 canvas.save(folder/('contact-'+str(start)+'.png'))
