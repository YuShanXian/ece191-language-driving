"""Read available map/control fields without asserting legal permission or changing choices."""
import json,sqlite3
from collections import Counter
from pathlib import Path
from mtr_project.paths import ROOT,sha256,write_json
from nuplan.common.maps.maps_datatypes import LaneConnectorType,StopLineType
import nuplan.common.maps.maps_datatypes as datatypes
import nuplan.database.nuplan_db.nuplan_scenario_queries as queries


def main():
    plan_path=ROOT/'runs/project-v2/turn-challenge-v1/window-plan.json';plan=json.loads(plan_path.read_text())
    map_path=ROOT/'data/nuplan/maps/us-nv-las-vegas-strip/9.15.1915/map.gpkg';records=[];windows=[]
    with sqlite3.connect(map_path.as_uri()+'?mode=ro',uri=True) as c:
        layers={name:[r[1] for r in c.execute(f'PRAGMA table_info({name})')] for name in ['lanes_polygons','lane_connectors','boundaries','stop_polygons','traffic_lights']}
        boundary_counts=dict(c.execute('SELECT boundary_type_fid,COUNT(*) FROM boundaries GROUP BY boundary_type_fid'))
        turn_counts={str(k):{'count':v,'sdk_enum':LaneConnectorType(k).name} for k,v in c.execute('SELECT turn_type_fid,COUNT(*) FROM lane_connectors GROUP BY turn_type_fid')}
        stop_counts={str(k):{'count':v,'sdk_enum':StopLineType(k).name} for k,v in c.execute('SELECT stop_polygon_type_fid,COUNT(*) FROM stop_polygons GROUP BY stop_polygon_type_fid')}
    sources={str(p.relative_to(ROOT)):sha256(p) for p in [plan_path,map_path]}
    for record in plan['records']:
        db=ROOT/'data/nuplan/db'/(record['clip']+'.db');sources[str(db.relative_to(ROOT))]=sha256(db)
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:
            total=dict(c.execute('SELECT status,COUNT(*) FROM traffic_light_status GROUP BY status'))
            records.append({'clip':record['clip'],'traffic_light_rows_by_status':total,'has_observed_states':bool(total)})
            for window in [w for w in plan['windows'] if w['clip']==record['clip']]:
                observations=c.execute('SELECT t.lane_connector_id,t.status FROM traffic_light_status t JOIN lidar_pc p ON p.record_id=t.lidar_pc_record_id WHERE p.timestamp=? ORDER BY t.lane_connector_id,t.status',(window['timestamp_us'],)).fetchall()
                windows.append({'window':window['key'],'clip':record['clip'],'timestamp_us':window['timestamp_us'],'connector_statuses':observations,
                                'status_counts':dict(Counter(status for _,status in observations)),
                                'duplicate_connector_ids':sorted(k for k,v in Counter(i for i,_ in observations).items() if v>1)})
    result={'scope':'Availability inventory only. No changes to candidate screening and no legal-compliance result. Exact current lidar timestamp; no future lights queried.',
            'layers':layers,'map_boundary_type_counts':boundary_counts,'boundary_enum_interpretation':'UNRESOLVED: no mapping found in inspected installed official map interface; do not guess dashed/solid permission.',
            'map_turn_types':turn_counts,'map_stop_types':stop_counts,'records':records,'windows':windows,'source_sha256':sources,
            'official_installed_sources':{str(Path(p)):sha256(p) for p in [datatypes.__file__,queries.__file__]},'generator_sha256':sha256(__file__)}
    output=ROOT/'runs/project-v2/catalog/map-control-availability.json';write_json(output,result)
    print(json.dumps({'records':records,'windows_with_exact_current_states':sum(bool(w['connector_statuses']) for w in windows),'windows':len(windows),'map_turn_types':turn_counts,'boundary_types_unresolved':boundary_counts},indent=2))


if __name__=='__main__':main()
