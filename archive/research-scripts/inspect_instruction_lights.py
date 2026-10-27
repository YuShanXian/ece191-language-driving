import sqlite3,json
from mtr_project.paths import ROOT
a=json.loads((ROOT/'runs/project-v3/instruction-priority-v5/results.json').read_text())
for w in a['windows']:
 c=json.loads((ROOT/'samples'/w['source_window']['sample']/'conversion.json').read_text())
 db=sqlite3.connect((ROOT/'data/nuplan/db'/f'{w["source_window"]["clip"]}.db').as_uri()+'?mode=ro',uri=True)
 if w['scene']==1:print(db.execute('PRAGMA table_info(traffic_light_status)').fetchall())
 print(w['scene'],c['current_timestamp_us'],db.execute('SELECT t.* FROM traffic_light_status t JOIN lidar_pc pc ON pc.record_id=t.lidar_pc_record_id WHERE pc.timestamp=? LIMIT 6',(c['current_timestamp_us'],)).fetchall())
 db.close()
