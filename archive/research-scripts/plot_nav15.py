import sys,json
from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,'historical-project/scripts')
from free_navigation_v8 import context
r=Path('historical-project');g,c,rot=context(7);cases=json.loads((r/'runs/project-v3/navigation-turn-v15/long-approach.json').read_text());fig,axs=plt.subplots(1,2,figsize=(15,7))
for ax,case in zip(axs,cases):
 e=case['result'];pts=np.array(e['points']);row=e['stages'][0]
 for n in g.nodes.values():
  line=(np.asarray(n.baseline.coords)[:,:2]-c[:2])@rot;ax.plot(*line.T,color='#d4dce3',lw=.8)
 ax.plot(*pts.T,color='#087f8c',lw=3);ax.scatter(*pts[0],color='black',s=45,zorder=3);ax.text(*pts[0],'  Start',fontsize=10);ax.scatter(*pts[-1],color='#d77b00',s=45,zorder=3);lo=pts.min(axis=0)-15;hi=pts.max(axis=0)+15;ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_aspect('equal');ax.grid(alpha=.2);ax.set_xlabel('Map x (m)');ax.set_ylabel('Map y (m)');ax.set_title('Turn '+('left' if row['action']=='turn_left' else 'right')+' command\nFollow road '+str(round(row['approach_distance_m']))+' m before turning')
fig.suptitle('Navigation turns: approach the junction along connected map roads',fontsize=17);fig.tight_layout();fig.savefig(r/'runs/project-v3/navigation-turn-v15/next-turn.png',dpi=160)
