"""Navigation-only expanded map, with geometrically validated missing junction links."""
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.affinity import translate
from pyproj import Transformer
from trajectory_checks import RoadGraph,RoadNode
from mtr_project.paths import ROOT
def load_graph(origin,epsg,map_path=None):
    p=Path(map_path) if map_path else ROOT/'data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg'
    if not p.is_absolute():p=ROOT/p
    transform=Transformer.from_crs(epsg,4326,always_xy=True)
    corners=[transform.transform(*(origin+[x,y])) for x in [-2500,2500] for y in [-2500,2500]]
    bbox=(min(q[0] for q in corners),min(q[1] for q in corners),max(q[0] for q in corners),max(q[1] for q in corners))
    def read(layer):return gpd.read_file(p,layer=layer,bbox=bbox,fid_as_index=True).to_crs(epsg=epsg)
    lanes=read('lanes_polygons');conn=read('gen_lane_connectors_scaled_width_polygons');links=read('lane_connectors');baselines=read('baseline_paths')
    lines={}
    for _,r in baselines.iterrows():
        if r.geometry.geom_type!='LineString':continue
        if pd.notna(r.lane_fid):key='L'+str(int(r.lane_fid))
        elif pd.notna(r.lane_connector_fid):key='C'+str(int(r.lane_connector_fid))
        else:continue
        lines[key]=translate(r.geometry,-origin[0],-origin[1])
    nodes=[];edges={}
    for _,r in lanes.iterrows():
        key='L'+str(int(r.lane_fid))
        if key not in lines:continue
        nodes.append(RoadNode(key,translate(r.geometry,-origin[0],-origin[1]),lines[key],
                              'lane',int(r.lane_group_fid),int(r.lane_index)))
    for _,r in conn.iterrows():
        key='C'+str(int(r.lane_connector_fid))
        if key in lines:nodes.append(RoadNode(key,translate(r.geometry,-origin[0],-origin[1]),lines[key],'connector'))
    keys={n.key for n in nodes}
    def add(a,b,relation):
        if a in keys and b in keys:edges.setdefault(a,{})[b]=relation
    for fid,r in links.iterrows():
        add('L'+str(int(r.exit_lane_fid)),'C'+str(int(fid)),'forward')
        add('C'+str(int(fid)),'L'+str(int(r.entry_lane_fid)),'forward')
    for _,group in lanes.groupby('lane_group_fid'):
        for _,a in group.iterrows():
            for _,b in group.iterrows():
                if abs(a.lane_index-b.lane_index)==1:
                    add('L'+str(int(a.lane_fid)),'L'+str(int(b.lane_fid)),
                        'left' if b.lane_index<a.lane_index else 'right')
    intersections=read('intersections')
    junctions=[translate(shape,-origin[0],-origin[1]) for shape in intersections.geometry if not shape.is_empty]
    from intersection_connections_v23 import complete_intersections
    return complete_intersections(nodes,edges,junctions)
