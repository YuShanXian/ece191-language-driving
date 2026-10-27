import json,pickle,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from mtr_project.paths import ROOT
from evaluate_candidate_checks import load_graph
base=ROOT/'runs/project-v3/instruction-priority-v6';out=base/'human-review'
font_manager.fontManager.addfont('/mnt/c/Windows/Fonts/msyh.ttc');plt.rcParams['font.family']=font_manager.FontProperties(fname='/mnt/c/Windows/Fonts/msyh.ttc').get_name();plt.rcParams['axes.unicode_minus']=False
names=['\u76f4\u884c\u6307\u4ee4','\u5de6\u8f6c\u6307\u4ee4','\u53f3\u8f6c\u6307\u4ee4','\u5411\u5de6\u6362\u9053\u6307\u4ee4','\u5411\u53f3\u6362\u9053\u6307\u4ee4']
for w in json.loads((base/'results.json').read_text())['windows']:
 missing=[j for j,c in enumerate(w['choices']) if c['status']!='destination_grounded_offline']
 if not missing:continue
 src=w['source_window'];run=ROOT/'runs'/src['run'];sample=ROOT/'samples'/src['sample'];c=json.loads((sample/'conversion.json').read_text());center=np.load(run/'internal_0000.npz')['center'];ego=pickle.load(open(sample/c['scenario'],'rb'))['tracks']['ego']['state'];g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);rot=np.array([[np.cos(center[6]),-np.sin(center[6])],[np.sin(center[6]),np.cos(center[6])]])
 for j in missing:
  fig,ax=plt.subplots(figsize=(11,8.5))
  for k,n in enumerate(g.nodes.values()):
   p=(np.asarray(n.baseline.coords)[:,:2]-center[:2])@rot;ax.plot(p[:,0],p[:,1],color='#cbd2d9',lw=1.2,label='\u5730\u56fe\u9053\u8def\u4e2d\u5fc3\u7ebf（\u4e0d\u662f\u8f66\u9053\u6807\u7ebf）' if k==0 else None)
  p=(ego['position'][:21,:2]-center[:2])@rot;ax.plot(p[:,0],p[:,1],color='#222',lw=3,label='\u8fc7\u53bb2\u79d2\u5b9e\u9645\u8def\u7ebf');ax.scatter(0,0,c='#222',s=70,label='\u5f53\u524d\u4f4d\u7f6e');ax.set_xlim(-15,55);ax.set_ylim(-25,35);ax.set_aspect('equal');ax.grid(alpha=.15);ax.legend(fontsize=11);ax.set_xlabel('\u6cbf\u5f53\u524d\u8f66\u5934\u65b9\u5411\u5411\u524d（\u7c73）');ax.set_ylabel('\u5411\u5de6（\u7c73）');ax.set_title(f'\u573a\u666f {w["scene"]:02d} · {names[j]}\n\u672c\u8f6e\u6ca1\u6709\u63d0\u4f9b\u9053\u8def\u8def\u7ebf：\u8bf7\u5224\u65ad\u4e0d\u6267\u884c\u662f\u5426\u5408\u7406',fontsize=17);fig.tight_layout();fig.savefig(out/f'scene-{w["scene"]:02d}-command-{j}.png',dpi=150);plt.close(fig)
print('6 no-output plots ready')
