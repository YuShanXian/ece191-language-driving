import sqlite3
from mtr_project.paths import ROOT
p=next((ROOT/'data/nuplan/db').glob('*.db'));c=sqlite3.connect(str(p));print(c.execute('pragma table_info(ego_pose)').fetchall());print(c.execute('select location,map_version from log').fetchall())
