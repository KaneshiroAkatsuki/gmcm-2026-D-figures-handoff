"""融合版科学图公共样式。只读本轮 v004 CSV/JSON；仅输出 PNG、SVG、CSV、JSON。"""
from pathlib import Path
import csv,json,hashlib,shutil,sys
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.ticker import MaxNLocator,FormatStrFormatter

HERE=Path(__file__).resolve().parent
DATA=HERE.parents[1]/'data'
RESULTS=HERE.parents[1]/'results'
WIDTH=15.5/2.54
C={'A':'#0072B2','B':'#D55E00','C':'#009E73','direct':'#3D697A','relay':'#CB8E3C','neutral':'#67737D'}
RES_KEYS=['drone_A','drone_B','drone_C','battery_A','battery_B','battery_C','relay','component']
RES_NAMES=['A型机','B型机','C型机','A型电池','B型电池','C型电池','中继机','中继组件']
plt.rcParams.update({'font.family':['Times New Roman','SimSun'],'font.size':10.5,
 'axes.titlesize':11,'axes.labelsize':10.5,'xtick.labelsize':10,'ytick.labelsize':10,
 'legend.fontsize':10,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
 'axes.edgecolor':'#657078','axes.linewidth':.7,'grid.color':'#DDE2E5','grid.linewidth':.5,
 'svg.fonttype':'none','savefig.facecolor':'white','figure.facecolor':'white',
 'mathtext.fontset':'stix','hatch.linewidth':.55})

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source(name):return DATA/(name+'.csv')
def read(name,stem):
 p=source(name);shutil.copyfile(p,HERE/(stem+'.csv'))
 return pd.read_csv(p,dtype=str,keep_default_na=False)
def num(df,col):return pd.to_numeric(df[col]).to_numpy(dtype=float)
def jread(name):return json.loads((RESULTS/(name+'.json')).read_text(encoding='utf-8'))
def grid(ax,axis='x'):
 ax.grid(axis=axis,zorder=0);ax.set_axisbelow(True)
def integer(ax,axis='x'):
 (ax.xaxis if axis=='x' else ax.yaxis).set_major_locator(MaxNLocator(integer=True))
def barlabels(ax,bars,fmt='.0f',pad=3,fontsize=10):
 ax.bar_label(bars,labels=[format(b.get_width(),fmt) for b in bars],padding=pad,fontsize=fontsize)
def hpanels(rows,ncols,height):
 fig,axs=plt.subplots(1,ncols,figsize=(WIDTH,height),sharey=True,layout='constrained')
 axs=np.atleast_1d(axs)
 for ax in axs: ax.set_yticks(np.arange(len(rows)),rows);grid(ax)
 axs[0].invert_yaxis()
 return fig,axs
def title(ax,s):ax.set_title(s,loc='left',pad=9)
def write_csv(stem,rows):
 p=HERE/(stem+'.csv')
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 return p
def save(fig,stem,caption,sources,qa,notes=''):
 fig.canvas.draw();renderer=fig.canvas.get_renderer();outside=[];undrawn_ticks=set()
 for ax in fig.axes:
  for axis,limits in [(ax.xaxis,ax.get_xlim()),(ax.yaxis,ax.get_ylim())]:
   low,high=sorted(limits)
   for tick in axis.get_major_ticks()+axis.get_minor_ticks():
    if not low-1e-10<=tick.get_loc()<=high+1e-10:undrawn_ticks.update([id(tick.label1),id(tick.label2)])
 for t in fig.findobj(Text):
  if t.get_visible() and t.get_text() and id(t) not in undrawn_ticks:
   b=t.get_window_extent(renderer)
   if b.x0 < -3 or b.y0 < -3 or b.x1 > fig.bbox.width+3 or b.y1 > fig.bbox.height+3:
    outside.append(t.get_text())
 fig.savefig(HERE/(stem+'.png'),dpi=300)
 fig.savefig(HERE/(stem+'.svg'))
 from PIL import Image
 im=Image.open(HERE/(stem+'.png'))
 meta={'stem':stem,'caption':caption,'numeric_version':'v004','png':stem+'.png','svg':stem+'.svg',
  'script':stem+'.py','data_csv':stem+'.csv','dpi':300,'width_cm':15.5,
  'pixel_size':list(im.size),'minimum_text_pt':min(t.get_fontsize() for t in fig.findobj(Text) if t.get_visible() and t.get_text()),
  'sources':[{'path':p.relative_to(HERE.parents[1]).as_posix(),'sha256':digest(p)} for p in sources],
  'qa':qa,'text_outside_figure':outside,'notes':notes}
 assert not outside, f'{stem}: text beyond figure bounds: {outside}'
 (HERE/(stem+'.meta.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
 plt.close(fig)
 print(stem,im.size,'PASS',flush=True)
