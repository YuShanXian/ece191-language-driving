import runpy
from pathlib import Path
p=Path(__file__).parent
for name in ['human_review_regression.py','semantic_regression.py','engine_regression.py','sequence_preview.py']:
 print('RUN',name,flush=True)
 try:runpy.run_path(str(p/name),run_name='__main__')
 except SystemExit as e:
  if e.code:raise
