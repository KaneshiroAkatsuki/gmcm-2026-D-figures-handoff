from common import *
stem='q2_task_energy';d=read('q2_tasks',stem);labels=list(d['架次'])
fig,axs=hpanels(labels,3,6.8);y=np.arange(len(d));colors=[C[x] for x in d['机型']]
for ax,col,lab in zip(axs,['能耗_kWh','载重_kg','返航SOC'],['(a) 能耗（kWh）','(b) 载重（kg）','(c) 返航荷电状态']):
 v=num(d,col);b=ax.barh(y,v,height=.6,color=colors,edgecolor='white',linewidth=.25,zorder=3);title(ax,lab)
 for patch,t in zip(b,d['机型']):patch.set_hatch({'A':'','B':'///','C':'xx'}[t])
 ax.set_xlim(0,max(v)*1.28);barlabels(ax,b,'.2f' if col!='载重_kg' else '.0f')
 if col=='返航SOC':ax.axvline(.2,color='#2D353A',ls='--',lw=.8)
from matplotlib.patches import Patch
fig.legend(handles=[Patch(facecolor=C[t],edgecolor='white',hatch={'A':'','B':'///','C':'xx'}[t],label=t+'型') for t in 'ABC'],loc='outside upper center',ncol=3,frameon=False)
raw=jread('q2');assert len(d)==len(raw['tasks'])==24
checks=all(abs(float(r['能耗_kWh'])-t['energy'])<1e-10 for (_,r),t in zip(d.iterrows(),raw['tasks']))
assert checks
save(fig,stem,'运输调度各任务能耗载荷与余量',[source('q2_tasks'),RESULTS/'q2.json'],{'tasks':len(d),'energy_total_kWh':float(num(d,'能耗_kWh').sum()),'minimum_return_soc':float(num(d,'返航SOC').min()),'task_energy_matches_frozen_json':checks},'固定24任务横向对照；未展示或推断搜索过程。荷电状态虚线为0.20。')
