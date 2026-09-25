from common import *
stem='legs_geometry';d=read('legs_o01',stem);fig,axs=hpanels(list(d['服务区']),3,5.15)
for ax,col,lab,color in zip(axs,['水平距离_m','去程爬升_m','去程下降_m'],['(a) 水平距离（m）','(b) 去程爬升（m）','(c) 去程下降（m）'],[C['A'],C['B'],C['C']]):
 vals=num(d,col)
 b=ax.barh(np.arange(len(d)),vals,color=color,height=.62,zorder=3);title(ax,lab);ax.set_xlim(0,max(vals)*1.26)
 barlabels(ax,b,'.0f' if col=='水平距离_m' else '.1f',fontsize=10)
save(fig,stem,'起降点至各服务区的航段几何',[source('legs_o01'),RESULTS/'q1.json'],{'sites':len(d),'distance_unit':'m','maximum_distance_m':float(num(d,'水平距离_m').max()),'no_new_route_computation':True},'只展示已存Q1去程几何；回程爬升和下降互换，水平距离相同。')
