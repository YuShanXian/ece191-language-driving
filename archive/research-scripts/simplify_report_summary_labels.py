import json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import ListedColormap,BoundaryNorm
from mtr_project.paths import ROOT
font_manager.fontManager.addfont('/mnt/c/Windows/Fonts/msyh.ttc');plt.rcParams['font.family']=font_manager.FontProperties(fname='/mnt/c/Windows/Fonts/msyh.ttc').get_name();plt.rcParams['axes.unicode_minus']=False
out=ROOT/'runs/project-v3/language-choice-v1/report-reviewed';a=json.loads((out/'evaluation.json').read_text());matrix=[[2 if c['choice']['candidate'] is not None else 1 if c['action_matching_before_other_screens'] else 0 for c in r['choices']] for r in a['windows']];labels=['\u76f4\u884c\u6307\u4ee4*','\u5de6\u8f6c\u6307\u4ee4','\u53f3\u8f6c\u6307\u4ee4','\u5411\u5de6\u6362\u9053\u6307\u4ee4','\u5411\u53f3\u6362\u9053\u6307\u4ee4']
fig,ax=plt.subplots(figsize=(14,8));ax.imshow([[3 if j==0 and v==2 else v for j,v in enumerate(row)] for row in matrix],cmap=ListedColormap(['#d9e0e6','#edb75f','#55ad91','#c8c6e6']),norm=BoundaryNorm([-.5,.5,1.5,2.5,3.5],4),aspect='auto');ax.set_xticks(range(5),labels,fontsize=13);ax.set_yticks(range(7),[f'\u573a\u666f {r["number"]:02d}' for r in a['windows']],fontsize=13)
for i,r in enumerate(a['windows']):
 for j,c in enumerate(r['choices']):
  chosen=c['choice']['candidate'];text=(f'\u6682\u4e0d\u80fd\u5224\u5b9a\u6210\u529f\n\u5df2\u9009\u8def\u7ebf #{chosen}' if j==0 else f'\u9009\u8def\u6d4b\u8bd5\u901a\u8fc7\n\u8def\u7ebf #{chosen}') if chosen is not None else ('\u6ca1\u6709\u9009\u51fa\u53ef\u7528\u8def\u7ebf\n\u5bf9\u5e94\u8def\u7ebf\u6ca1\u901a\u8fc7\u68c0\u67e5' if matrix[i][j]==1 else '\u6ca1\u6709\u9009\u51fa\u53ef\u7528\u8def\u7ebf\n\u672a\u627e\u5230\u7b26\u5408\u8981\u6c42\u7684\u8def\u7ebf');ax.text(j,i,text,ha='center',va='center',fontsize=12)
ax.set_title('\u6bcf\u6761\u6307\u4ee4\u7684\u6d4b\u8bd5\u7ed3\u8bba：\u901a\u8fc7、\u6ca1\u6709\u53ef\u7528\u8f93\u51fa，\u8fd8\u662f\u6682\u4e0d\u80fd\u5224\u5b9a？',fontsize=19,pad=20);fig.text(.025,.02,'\u901a\u8fc7=\u9009\u51fa\u4e86\u7b26\u5408\u52a8\u4f5c\u89c4\u5219\u4e14\u901a\u8fc7\u5f53\u524d\u68c0\u67e5\u7684\u8def\u7ebf；\u7d2b\u8272=\u76f4\u884c\u5224\u65ad\u5c1a\u4e0d\u53ef\u9760，\u4e0d\u80fd\u8ba1\u4e3a\u6210\u529f。\u5747\u672a\u6d4b\u8bd5\u8f66\u8f86\u5b9e\u9645\u6267\u884c。',fontsize=12);fig.tight_layout(rect=[0,.06,1,1]);fig.savefig(out/'choice-matrix.png',dpi=160);plt.close(fig)
selected=np.sum(np.array(matrix)==2,axis=0);rejected=np.sum(np.array(matrix)==1,axis=0);none=7-selected-rejected;x=np.arange(5)
fig,ax=plt.subplots(figsize=(13,7));ax.bar(x,selected,color='#55ad91',label='\u9009\u4e2d\u4e86\u8def\u7ebf');ax.bar(x,rejected,bottom=selected,color='#edb75f',label='\u6709\u5bf9\u5e94\u8def\u7ebf，\u4f46\u6ca1\u901a\u8fc7\u68c0\u67e5');ax.bar(x,none,bottom=selected+rejected,color='#d9e0e6',label='\u68c0\u67e5\u7a0b\u5e8f\u672a\u627e\u5230\u7b26\u5408\u6307\u4ee4\u7684\u8def\u7ebf');ax.set_xticks(x,labels,fontsize=13);ax.set_ylim(0,8.5);ax.set_ylabel('\u573a\u666f\u6570（\u51717\u4e2a）',fontsize=14);ax.set_title('\u6bcf\u6761\u6307\u4ee4\u57287\u4e2a\u573a\u666f\u4e2d\u7684\u9009\u62e9\u7ed3\u679c',fontsize=20)
for i,n in enumerate(selected):ax.text(i,7.2,f'{n}\u4e2a\u573a\u666f\u9009\u51fa\u4e86\u8def\u7ebf',ha='center',fontsize=12)
ax.legend(loc='upper center',bbox_to_anchor=(.5,-.1),ncol=1,fontsize=12);fig.tight_layout();fig.savefig(out/'coverage.png',dpi=160);plt.close(fig)
print('Updated summary figures; evaluation unchanged')
