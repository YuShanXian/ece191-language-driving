"""Neutral one-at-a-time figures for user review; no automatic verdict displayed."""
import argparse,json,pickle
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from evaluate_candidate_checks import load_graph
from mtr_project.paths import ROOT
p=argparse.ArgumentParser();p.add_argument('--scene',type=int,required=True);p.add_argument('--command',type=int,required=True);args=p.parse_args()
base=ROOT/'runs/project-v3/language-choice-v1/report-reviewed';a=json.loads((base/'evaluation.json').read_text());r=next(r for r in a['windows'] if r['number']==args.scene);choice=r['choices'][args.command];w=r['source_window'];folder=ROOT/'samples'/w['sample'];run=ROOT/'runs'/w['run'];c=json.loads((folder/'conversion.json').read_text());ego=pickle.load(open(folder/c['scenario'],'rb'))['tracks']['ego']['state'];g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map']);center=np.load(run/'internal_0000.npz')['center'];xy=np.load(run/'refined_v2_candidates.npz')['world_xy'];h=center[6];rotation=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]]);local=lambda q:(np.asarray(q)[...,:2]-center[:2])@rotation
font_manager.fontManager.addfont('/mnt/c/Windows/Fonts/msyh.ttc');plt.rcParams['font.family']=font_manager.FontProperties(fname='/mnt/c/Windows/Fonts/msyh.ttc').get_name();plt.rcParams['axes.unicode_minus']=False
labels=['\u76f4\u884c','\u5de6\u8f6c','\u53f3\u8f6c','\u5411\u5de6\u6362\u9053','\u5411\u53f3\u6362\u9053'];fig,ax=plt.subplots(figsize=(10,8))
for k,node in enumerate(g.nodes.values()):
 q=local(node.baseline.coords);ax.plot(q[:,0],q[:,1],color='#cbd3dc',lw=1,label='nuPlan\u5730\u56fe\u4e2d\u5fc3\u7ebf' if k==0 else None)
past=local(ego['position'][:21,:2]);ax.plot(past[:,0],past[:,1],color='#222',lw=2.5,label='\u8f66\u8f86\u8fc7\u53bb2\u79d2\u7684\u5b9e\u9645\u8def\u7ebf');ax.scatter(0,0,s=65,color='#e09928',zorder=10,label='\u5f53\u524d\u4f4d\u7f6e')
selected=choice['choice']['candidate']
if selected is not None:
 q=local(np.vstack([center[:2],xy[selected-1]]));ax.plot(q[:,0],q[:,1],color='#246ab1',lw=3.5,label=f'\u9009\u62e9\u7a0b\u5e8f\u8f93\u51fa\u7684\u8def\u7ebf #{selected}');extent=np.vstack([past,q])
else:extent=np.vstack([past,local(ego['position'][20:81,:2])]);ax.text(.5,.92,'\u9009\u62e9\u7a0b\u5e8f\u6ca1\u6709\u8f93\u51fa\u8def\u7ebf',transform=ax.transAxes,ha='center',fontsize=17,bbox={'facecolor':'white','edgecolor':'#aaa'})
lo=extent.min(axis=0)-15;hi=extent.max(axis=0)+15;span=np.maximum(hi-lo,50);middle=(lo+hi)/2;ax.set_xlim(middle[0]-span[0]/2,middle[0]+span[0]/2);ax.set_ylim(middle[1]-span[1]/2,middle[1]+span[1]/2);ax.set_aspect('equal');ax.grid(alpha=.15);ax.tick_params(labelsize=13);ax.set_xlabel('\u6cbf\u5f53\u524d\u8f66\u5934\u65b9\u5411\u5411\u524d（\u7c73）',fontsize=14);ax.set_ylabel('\u5411\u5de6（\u7c73）',fontsize=14);ax.set_title(f'\u4eba\u5de5\u8bc4\u5ba1 {(args.scene-1)*5+args.command+1}/35 · \u573a\u666f {args.scene:02d}\n\u8f93\u5165\u6307\u4ee4：{labels[args.command]}（{choice["instruction"]}）',fontsize=19,pad=18);ax.legend(fontsize=11,loc='upper left');fig.tight_layout();dest=base/'human-review';dest.mkdir(exist_ok=True);path=dest/f'scene-{args.scene:02d}-command-{args.command}.png';fig.savefig(path,dpi=160);print(path)
