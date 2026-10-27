from pathlib import Path
import sqlite3,pickle,json
import geopandas as gpd
root=Path('historical-project')
p=root/'data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg'
for layer in ['baseline_paths','boundaries','lanes_polygons','lane_connectors','meta']:
    d=gpd.read_file(p,layer=layer,rows=2)
    print(layer,'crs',getattr(d,'crs',None),'cols',list(d),d.drop(columns=['geometry'],errors='ignore').to_string())
s=pickle.load(open(next((root/'samples/val').glob('sd_*.pkl')),'rb'))
print('METADATA',[(k,str(v)[:220]) for k,v in s['metadata'].items()])
t=next(iter(s['tracks'].values()))
print('TRACK',[(k,v) for k,v in t.items() if k!='state'])
print('STATE',[(k,v.shape,str(v.flatten()[:3])) for k,v in t['state'].items()])
print('SUMMARY',str(pickle.load(open(root/'samples/val/dataset_summary.pkl','rb')))[:1200])

