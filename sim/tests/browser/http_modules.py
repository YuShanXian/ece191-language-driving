import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
"""Check that the deployed entry point and every imported ES module can load."""
from urllib.request import urlopen
from urllib.parse import urljoin
import re,json
seen=set()
def check(url):
 if url in seen:return
 seen.add(url)
 with urlopen(url,timeout=10) as response:
  assert response.status==200
  assert 'javascript' in response.headers.get('Content-Type','')
  source=response.read().decode()
 for imported in re.findall(r"from\s+['\"]([^'\"]+)['\"]",source):check(urljoin(url,imported))
check('http://localhost:8776/app.js')
print(json.dumps({'loaded_modules':sorted(seen),'passed':True}))
