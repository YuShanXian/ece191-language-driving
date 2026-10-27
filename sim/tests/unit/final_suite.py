import runpy
from pathlib import Path
root=Path(__file__).parent
for name in ['lateral_regression.py','run_map_suite.py']:
    runpy.run_path(str(root/name),run_name='__main__')
