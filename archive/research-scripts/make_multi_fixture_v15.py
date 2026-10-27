import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,'historical-project/scripts')
from free_navigation_v8 import context
from trajectory_checks import tangent
r=Path('historical-project');g,c,rot=context(7)
lanes=[n for n in g.nodes.values() if n.kind=='lane' and n.baseline.length>50 and np.linalg.norm(np.array(n.baseline.interpolate(20).coords[0])[:2]-c[:2])<1500]
n=min(lanes,key=lambda n:np.linalg.norm(np.array(n.baseline.interpolate(20).coords[0])[:2]-c[:2]));p=np.array(n.baseline.interpolate(20).coords[0])[:2];hist=np.array([n.baseline.interpolate(float(s)).coords[0][:2] for s in np.arange(0,20.1,.5)]);state={'xy':((p-c[:2])@rot).tolist(),'heading':float(tangent(n.baseline,p)-c[6]),'speed':0.,'history':((hist-c[:2])@rot).tolist()};out=r/'runs/project-v3/multistep-v15';out.mkdir(exist_ok=True);(out/'state.json').write_text(json.dumps(state));print(n.key,n.baseline.length,state['xy'])

