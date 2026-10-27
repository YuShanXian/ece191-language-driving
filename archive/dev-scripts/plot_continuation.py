from fixtures import load_scene
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
s=load_scene(1); fig,ax=plt.subplots(figsize=(12,8))
for k,n in s.nodes.items():
 if k.startswith('J_'):continue
 x,y=n.baseline.xy
 if n.baseline.bounds[0]<150 and n.baseline.bounds[2]>55 and n.baseline.bounds[1]<10 and n.baseline.bounds[3]>-50:
  ax.plot(x,y,color='#c4cbd1',linewidth=.8)
for i,k in enumerate(['L67619','C70254','L67605','C69782','L67695','C69338','C70265','L67625','C69923','C69753','L67751','C70301','L67733']):
 n=s.nodes[k];x,y=n.baseline.xy; ax.plot(x,y,label=k,linewidth=2.3); p=n.baseline.interpolate(.5,normalized=True);ax.text(p.x,p.y,k,fontsize=8)
ax.set_xlim(55,122);ax.set_ylim(-45,3);ax.set_aspect('equal');ax.grid(alpha=.2)
fig.savefig(Path(__file__).parents[1]/'results/continuation-map.png',dpi=140)
