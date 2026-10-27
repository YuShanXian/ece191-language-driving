import json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
r=Path('historical-project');sys.path.insert(0,str(r/'scripts'));out=r/'runs/project-v3/command-audit-v17'
from free_navigation_v8 import context
from execute_language_plan_v4 import execute
g,c,rot=context(7)
for name,id in [('right-lane-turn','654cb1d6-fa5f-4d7d-8f9e-6b4ac7f18ae8'),('already-in-left-bend','e66842f5-f490-45d4-900c-6959cc39a48b')]:
 d=r/'runs/project-v3/provider-benchmark-20261020/raw'/id;state=json.loads((d/'start-state.json').read_text());plan=json.loads((d/'parsed.json').read_text());e=execute(7,plan,state,'free');(out/(name+'.json')).write_text(json.dumps(e));print(name,e['status'],[s.get('reason') for s in e.get('stages',[])],flush=True)
 pp=np.asarray(e['points']);fig,ax=plt.subplots(figsize=(11,8));
 for n in g.nodes.values():
  xy=(np.asarray(n.baseline.coords)[:,:2]-c[:2])@rot;ax.plot(xy[:,0],xy[:,1],color='#ced5dc',lw=1)
 ax.plot(pp[:,0],pp[:,1],color='#007e91',lw=3,label='New planned trajectory');ax.scatter(*pp[0],s=90,c='black',zorder=4,label='Actual position when command was sent');ax.scatter(*pp[-1],s=80,c='#ed8a16',zorder=4,label='Maneuver end; road following can continue');ax.set_xlim(pp[:,0].min()-18,pp[:,0].max()+18);ax.set_ylim(pp[:,1].min()-18,pp[:,1].max()+18);ax.set_aspect('equal');ax.grid(alpha=.18);ax.legend(loc='best');ax.set_xlabel('Scene x (m)');ax.set_ylabel('Scene y (m)');ax.set_title('Original input: '+json.loads((d/'request.json').read_text())['instruction']+'\n'+('Change right lane, then turn at the junction' if name.startswith('right') else 'Continue the left turn already entered'));fig.tight_layout();fig.savefig(out/(name+'.png'),dpi=150);plt.close(fig)
