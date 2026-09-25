from common import *
stem='q3_relay_energy';d=read('q3_relays',stem);fig,axs=hpanels(list(d['中继架次']),2,3.4)
for ax,col,lab,color in zip(axs,['能耗_kWh','返航SOC'],['(a) 总能耗（kWh）','(b) 返航荷电状态'],[C['B'],C['A']]):
 v=num(d,col);b=ax.barh(np.arange(len(d)),v,height=.60,color=color,zorder=3);title(ax,lab);ax.set_xlim(0,v.max()*1.3);barlabels(ax,b,'.3f')
 if col=='返航SOC':ax.axvline(.2,color='#303A41',ls='--',lw=.8)
raw=jread('q3')['relays'];assert len(d)==len(raw)==6
save(fig,stem,'中继任务能耗与返航余量',[source('q3_relays'),RESULTS/'q3.json'],{'relay_tasks':len(d),'energy_total_kWh':float(num(d,'能耗_kWh').sum()),'minimum_return_soc':float(num(d,'返航SOC').min()),'energy_matches_json':all(abs(float(r['能耗_kWh'])-t['energy'])<1e-10 for (_,r),t in zip(d.iterrows(),raw))},'中继任务总能耗包括题定运行阶段；荷电状态虚线为0.20。')

