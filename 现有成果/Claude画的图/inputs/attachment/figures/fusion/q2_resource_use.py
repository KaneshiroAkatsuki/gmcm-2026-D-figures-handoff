from common import *
stem='q2_resource_use';d=read('q2_resources',stem)
fig,axs=plt.subplots(2,2,figsize=(WIDTH,7.1),gridspec_kw={'height_ratios':[8,14]},layout='constrained')
for row,kind in enumerate(['无人机','电池']):
 s=d[d['类别']==kind];y=np.arange(len(s));labels=[v.replace('-BAT-','-') for v in s['资源']]
 for ax,col,lab in zip(axs[row],['使用次数','占用时间_s'],['使用次数','占用时长（s）']):
  vals=num(s,col)
  b=ax.barh(y,vals,color=C['A'] if row==0 else C['B'],height=.6,zorder=3)
  ax.set_yticks(y,labels);ax.invert_yaxis();grid(ax);title(ax,f'({"abcd"[row*2+list(axs[row]).index(ax)]}) {kind}{lab}')
  ax.set_xlim(0,max(vals)*1.35);barlabels(ax,b,'.0f')
  if col=='使用次数':integer(ax)
tasks=jread('q2')['tasks'];checks=[]
for _,r in d.iterrows():
 if r['类别']=='无人机':
  raw=sum(t['return_time']-t['start'] for t in tasks if t['drone']==r['资源'])
  checks.append(abs(raw-float(r['占用时间_s']))<1e-8)
assert all(checks)
save(fig,stem,'运输实体与电池的使用情况',[source('q2_resources'),RESULTS/'q2.json'],{'resources':len(d),'drone_count':int((d['类别']=='无人机').sum()),'battery_count':int((d['类别']=='电池').sum()),'time_unit':'s','drone_task_occurrences':int(num(d[d['类别']=='无人机'],'使用次数').sum()),'battery_task_occurrences':int(num(d[d['类别']=='电池'],'使用次数').sum()),'drone_occupancy_directly_recomputed_from_json':all(checks)},'运输实体从准备开始占用至返航，不加额外周转；电池占用延续至充满。分别累计，不把二者相加为同类资源。电池标签省略BAT。')
