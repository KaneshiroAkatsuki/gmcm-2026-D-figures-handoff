from common import *
stem='q4_nocopy';a=next(x for x in jread('q4')['selected'] if x['K']==3);b=next(x for x in jread('q4_no_copy_sensitivity')['selected'] if x['K']==3)
rows=[{'资源':n,'允许复制缺口':a['shortage'][k],'禁止复制缺口':b['shortage'][k],'缺口变化':b['shortage'][k]-a['shortage'][k]} for k,n in zip(RES_KEYS,RES_NAMES)];write_csv(stem,rows);d=pd.DataFrame(rows)
fig,axs=hpanels(RES_NAMES,3,3.8);y=np.arange(8)
for ax,col,lab,color in zip(axs,['允许复制缺口','禁止复制缺口','缺口变化'],['(a) 允许复制','(b) 禁止复制','(c) 禁止 − 允许'],[C['A'],C['B'],C['C']]):
 v=num(d,col);bars=ax.barh(y,v,color=[color if x>=0 else '#8C5A92' for x in v],height=.62,zorder=3)
 title(ax,lab);integer(ax);ax.set_xlabel('库存缺口（件）' if col!='缺口变化' else '缺口变化（件）')
 ax.set_xlim(min(-.45,v.min()-.65),max(1,v.max()+.7));ax.axvline(0,color='#61717B',lw=.7)
 for yy,val in zip(y,v):ax.text(val+(.07 if val>=0 else -.07),yy,f'{val:+.0f}' if col=='缺口变化' else f'{val:.0f}',ha='left' if val>=0 else 'right',va='center',fontsize=10)
delta=int(num(d,'缺口变化').sum());fig.suptitle(f'三组方案：库存缺口净变化 {delta:+d} 件',fontsize=11)
assert delta==2
save(fig,stem,'禁止中继任务复制对三组库存缺口的影响',[RESULTS/'q4.json',RESULTS/'q4_no_copy_sensitivity.json'],{'copy_shortage_total':int(num(d,'允许复制缺口').sum()),'no_copy_shortage_total':int(num(d,'禁止复制缺口').sum()),'net_shortage_change':delta,'all_eight_categories_preserved':True},'固定Q3任务、时刻与保障关系，仅比较两种已存Q4解释；不同资源项可增可减，净缺口增加2件。')
