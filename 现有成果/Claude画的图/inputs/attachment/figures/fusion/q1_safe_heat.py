from common import *
stem='q1_safe_heat';d=read('q1_safe_payload_rho020',stem);a=np.array([num(d,f'{t}_kg') for t in 'ABC']).T
fig,ax=plt.subplots(figsize=(WIDTH,5.5),layout='constrained');im=ax.imshow(a,cmap='Blues',aspect='auto',vmin=0,vmax=a.max())
ax.set_xticks(range(3),['A型','B型','C型']);ax.set_yticks(range(len(d)),d['服务区']);ax.tick_params(length=0)
for i in range(len(d)):
 for j in range(3):
  v=a[i,j];ax.text(j,i,f'{v:.3f}',ha='center',va='center',fontsize=10,color='white' if v>a.max()*.64 else '#18242C')
ax.set_title('安全余量比例 0.20；载荷单位 kg',pad=12)
cb=fig.colorbar(im,ax=ax,shrink=.78,pad=.04);cb.set_label('安全载荷上限（kg）')
save(fig,stem,'三机型各服务区安全载荷上限',[source('q1_safe_payload_rho020')],{'shape':list(a.shape),'values_equal_source':True,'minimum_kg':float(a.min()),'maximum_kg':float(a.max())},'图中保留源CSV三位小数；颜色仅辅助比较，45格均注值。')

