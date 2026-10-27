from audit_scene_context import ROOT,metadata
m,e=metadata(ROOT/'data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg')
for k in ['C69047','C68780']:print(k,m[k])
