from common import *
stem='q3_backhaul';q=jread('q3');bc=q['communication']['backhaul_certificates'];bound=q['communication']['delta_g_db']
rows=[{'中继架次':r['id'],'回传裕量下界_dB':bc[r['id']]['margin_lower_db'],'稳健判定门限_dB':bound} for r in q['relays']];write_csv(stem,rows)
d=pd.DataFrame(rows);v=num(d,'回传裕量下界_dB');fig,ax=plt.subplots(figsize=(WIDTH,3.35),layout='constrained')
b=ax.barh(np.arange(len(d)),v,color=C['A'],height=.6,zorder=3);ax.set_yticks(np.arange(len(d)),d['中继架次']);ax.invert_yaxis();grid(ax)
ax.set_xlim(0,v.max()*1.2);ax.set_xlabel('回传链路裕量下界（dB）');barlabels(ax,b,'.3f')
ax.axvline(bound,color='#202C33',ls='--',lw=1,label=f'稳健判定门限 {bound:.2f} dB');ax.legend(loc='lower right',frameon=False)
save(fig,stem,'六个中继任务的回传裕量下界',[RESULTS/'q3.json'],{'relay_certificates':len(d),'minimum_backhaul_bound_db':float(v.min()),'all_backhaul_bounds_above_guard':bool(np.all(v>=bound))},'只展示中继至地面站的回传链路下界；不把其中最小值称为全部通信链路最小裕量。')

