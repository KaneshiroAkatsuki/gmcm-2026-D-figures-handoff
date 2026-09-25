from common import *
stem='q4_balance';rows=[]
for fn,policy in [('q4','复制'),('q4_no_copy_sensitivity','禁复制')]:
 q=jread(fn)
 for collection,select in [('selected','资源'),('alternative_selected','均衡')]:
  for s in q[collection]:
   rows.append({'方案':f'{policy}{s["K"]}组·{select}','口径':policy,'分组数':s['K'],'选择顺序':select,'实体数':sum(s['total'][k] for k in ['drone_A','drone_B','drone_C','relay']),'能源件数':sum(s['total'][k] for k in ['battery_A','battery_B','battery_C','component']),'库存缺口':sum(s['shortage'].values()),'工作量CV':s['workload_cv']})
write_csv(stem,rows);d=pd.DataFrame(rows);y=np.arange(len(d));colors=[C['A'] if s=='复制' else C['B'] for s in d['口径']]
fig,axs=plt.subplots(2,2,figsize=(WIDTH,6.4),layout='constrained',sharey=True)
for i,(ax,col,lab) in enumerate(zip(axs.flat,['实体数','能源件数','库存缺口','工作量CV'],['(a) 实体数（架）','(b) 能源件数','(c) 库存缺口（件）','(d) 工作量变异系数'])):
 v=num(d,col);b=ax.barh(y,v,color=colors,height=.60,zorder=3);ax.set_yticks(y,d['方案']);grid(ax);title(ax,lab);ax.set_xlim(0,v.max()*1.28)
 barlabels(ax,b,'.3f' if col=='工作量CV' else '.0f')
 if col!='工作量CV':integer(ax)
axs[0,0].invert_yaxis()
save(fig,stem,'八个入选分区方案的资源与均衡比较',[RESULTS/'q4.json',RESULTS/'q4_no_copy_sensitivity.json'],{'selected_plans':len(rows),'source_collections':['selected','alternative_selected'],'all_quantities_directly_aggregated_from_current_json':True},'资源与均衡分别表示当前两种字典序选择；不是重算搜索轨迹，不称为完整帕累托前沿。')

