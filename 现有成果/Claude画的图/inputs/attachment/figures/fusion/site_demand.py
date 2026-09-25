from common import *
stem='site_demand';d=read(stem,stem);d=d[d['节点']!='O01']
fig,axs=hpanels(list(d['节点']),3,5.1)
for ax,col,lab,color in zip(axs,['总质量_kg','总体积_m3','箱数'],['(a) 总质量（kg）','(b) 总体积（m³）','(c) 箱数'],[C['A'],C['B'],C['C']]):
 vals=num(d,col);b=ax.barh(np.arange(len(d)),vals,color=color,height=.62,zorder=3)
 title(ax,lab);ax.set_xlim(0,max(vals)*1.28);barlabels(ax,b,'.3f' if col=='总体积_m3' else '.0f',fontsize=10)
 if col=='箱数':integer(ax)
save(fig,stem,'各服务区物资质量体积与箱数',[source(stem)],{'sites':len(d),'boxes_total':int(num(d,'箱数').sum()),'mass_total_kg':float(num(d,'总质量_kg').sum()),'volume_total_m3':float(num(d,'总体积_m3').sum()),'all_boxes':int(num(d,'箱数').sum())==80})

