from common import *
stem='q4_redundancy';q=jread('q4');rows=[];a=[];labels=[]
for s in q['selected']:
 for metric,label in [('redundancy','冗余'),('shortage','库存缺口')]:
  vals=[s[metric][k] for k in RES_KEYS];a.append(vals);labels.append(f'{s["K"]}组 · {label}')
  for k,n,v in zip(RES_KEYS,RES_NAMES,vals):rows.append({'分组数':s['K'],'指标':label,'资源':n,'数量':v,'不分区用量':q['baseline_resources'][k],'现有库存':q['inventory'][k],'分区需求':s['total'][k]})
write_csv(stem,rows);a=np.array(a)
fig,ax=plt.subplots(figsize=(WIDTH,3.15),layout='constrained');ax.imshow(a,cmap='Blues',vmin=0,vmax=max(1,a.max()),aspect='auto')
ax.set_xticks(range(8),RES_NAMES,rotation=35,ha='right');ax.set_yticks(range(4),labels);ax.tick_params(length=0)
for i in range(4):
 for j in range(8):ax.text(j,i,str(a[i,j]),ha='center',va='center',fontsize=11,color='white' if a[i,j]>a.max()*.6 else '#17232B')
ax.set_title('冗余相对于不分区；缺口相对于现有库存',loc='left',pad=12)
save(fig,stem,'两组与三组配置的冗余及库存缺口',[RESULTS/'q4.json'],{'matrix_shape':list(a.shape),'K2_shortage':int(a[1].sum()),'K3_shortage':int(a[3].sum()),'all_values_exactly_from_selected':True},'只画主口径资源优先的两组、三组方案；各类资源逐项区分。')

