from common import *
from decimal import Decimal,localcontext
stem='q3_comm_share';q=jread('q3');tot={t['id']:{'direct':Decimal(0),'relay':Decimal(0),'count':0} for t in q['tasks']}
with localcontext() as ctx:
 ctx.prec=110
 for s in q['nominal_communication']['intervals']:
  dt=Decimal(s['end_exact_decimal'])-Decimal(s['start_exact_decimal']);assert dt>=0
  mode='direct' if s['mode']=='direct' else 'relay'
  assert s['mode'] in ['direct','relay']
  tot[s['task']][mode]+=dt;tot[s['task']]['count']+=1
 rows=[]
 for t in q['tasks']:
  s=tot[t['id']];whole=s['direct']+s['relay'];expected=sum(e['end']-e['start'] for e in t['events'] if e['phase']!='准备装载')
  assert abs(float(whole)-expected)<1e-8
  rows.append({'运输任务':t['id'],'直连时长_s':str(s['direct']),'中继时长_s':str(s['relay']),'总时长_s':str(whole),'直连份额':str(s['direct']/whole),'中继份额':str(s['relay']/whole),'状态段数':s['count']})
write_csv(stem,rows)
d=pd.DataFrame(rows);direct=num(d,'直连份额')*100;relay=num(d,'中继份额')*100;y=np.arange(len(d))
fig,ax=plt.subplots(figsize=(WIDTH,7.1),layout='constrained')
ax.barh(y,direct,height=.65,color=C['direct'],label='直连',zorder=3)
ax.barh(y,relay,left=direct,height=.65,color=C['relay'],hatch='///',edgecolor='white',lw=.2,label='中继',zorder=3)
ax.set_yticks(y,d['运输任务']);ax.invert_yaxis();ax.set_xlim(0,114);ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('通信保障累计时长份额（%）');grid(ax)
for yy,v in zip(y,direct):ax.text(102,yy,f'{v:.1f}',va='center',ha='left',fontsize=10)
ax.set_title('右侧数值为直连份额（%）',loc='left',pad=10)
ax.legend(loc='outside upper center' if False else 'lower right',frameon=False,bbox_to_anchor=(1.0,1.005),ncol=2)
alltime=num(d,'总时长_s').sum();directtime=num(d,'直连时长_s').sum()
save(fig,stem,'各运输任务直连与中继保障份额',[RESULTS/'q3.json'],{'transport_tasks':len(d),'nominal_intervals':int(num(d,'状态段数').sum()),'duration_total_s':float(alltime),'direct_duration_s':float(directtime),'direct_share':float(directtime/alltime),'each_task_duration_equals_airborne_and_handover_events':True,'boundary_points_add_zero_duration':True},'按名义开区间累加；并发任务各自计时，合计不是日历完工时间。边界点不重复赋时长。')

