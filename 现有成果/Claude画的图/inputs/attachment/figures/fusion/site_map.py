from common import *
stem='site_map';d=read('site_demand',stem);s=d[d['节点']!='O01'];o=d[d['节点']=='O01'].iloc[0]
fig,ax=plt.subplots(figsize=(WIDTH,4.9),layout='constrained')
x=num(s,'经度');y=num(s,'纬度');mass=num(s,'总质量_kg')
ax.scatter(x,y,s=mass*2.6,facecolor='#E9F0F3',edgecolor=C['direct'],linewidth=1.2,zorder=3)
for xx,yy,label in zip(x,y,s['节点']):
 ax.annotate(label,(xx,yy),xytext=(5,7),textcoords='offset points',fontsize=10,zorder=4)
ax.scatter([float(o['经度'])],[float(o['纬度'])],marker='*',s=175,color='#B84438',zorder=5)
ax.annotate('O01 起降点',(float(o['经度']),float(o['纬度'])),xytext=(-30,-20),textcoords='offset points',fontsize=10)
ax.set_xlabel('经度（°E）');ax.set_ylabel('纬度（°N）')
ax.xaxis.set_major_formatter(FormatStrFormatter('%.3f'));ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
ax.set_aspect(1/np.cos(np.deg2rad(np.mean(y))))
ax.margins(x=.16,y=.19);grid(ax,'both')
ax.annotate('北',xy=(.94,.91),xytext=(.94,.78),xycoords='axes fraction',ha='center',arrowprops={'arrowstyle':'->','lw':1})
ax.text(.03,.97,'圆面积对应物资总质量',transform=ax.transAxes,va='top',fontsize=10)
save(fig,stem,'起降点与服务区需求空间分布',[source('site_demand')],{'service_sites':len(s),'origin_count':1,'mass_total_kg':float(mass.sum()),'rows_match_original_csv':len(d)==16},'气泡面积与质量成线性关系；坐标来自原始节点表，不含外部地图。')
