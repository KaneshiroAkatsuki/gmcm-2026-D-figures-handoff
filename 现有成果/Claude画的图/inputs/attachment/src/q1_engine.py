import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dcore import *
import sys,time,platform
from scipy.optimize import milp,LinearConstraint,Bounds
from scipy.sparse import csc_matrix,vstack


def candidates(m,site,rho):
    ids=[k for k,b in m.boxes.items() if b['site']==site];n=len(ids)
    candidates=[];cols=[];rr=[];cc=[]
    for mask in range(1,1<<n):
        ix=[i for i in range(n) if mask>>i&1];bs=[ids[i] for i in ix]
        mass=sum(m.boxes[i]['mass'] for i in bs);vol=sum(m.boxes[i]['volume'] for i in bs)
        for gid,g in m.types.items():
            if mass>g['capacity']+1e-9 or vol>g['volume']+1e-9:continue
            go=leg(g,m.geo['O01',site],mass);back=leg(g,m.geo[site,'O01'],0)
            energy=go['energy']+back['energy']
            if energy>(1-rho)*g['energy']+1e-10:continue
            duration=g['prep']+g['load_box']*len(bs)+go['time']+g['handover_base']+g['handover_box']*len(bs)+back['time']
            j=len(candidates);rr.extend(ix);cc.extend([j]*len(ix));candidates.append(dict(type=gid,boxes=bs,energy=energy,duration=duration,mask=mask))
    mat=csc_matrix((np.ones(len(rr)),(rr,cc)),shape=(n,len(candidates)))
    return candidates,mat

def q1_solve(m,rho=.2,priority='sorties_energy'):
    tasks=[];logs=[]
    for site in sorted(set(b['site'] for b in m.boxes.values())):
        cand,A=candidates(m,site,rho);n=len(cand)
        if not n:raise ValueError(f'{site}: 无候选')
        con=[LinearConstraint(A,np.ones(A.shape[0]),np.ones(A.shape[0]))]
        objs=[np.ones(n),np.array([c['energy'] for c in cand])] if priority=='sorties_energy' else [np.array([c['energy'] for c in cand]),np.ones(n)]
        # 明确只选两级优先目标；累计作业时间单列报告，不声称三目标同时最优。
        states=[]
        for step,c in enumerate(objs):
            res=milp(c,integrality=np.ones(n),bounds=Bounds(0,1),constraints=con,options=dict(time_limit=60,mip_rel_gap=0))
            if res.x is None:raise RuntimeError((site,res.message))
            states.append(dict(status=int(res.status),message=res.message,objective=float(res.fun),bound=float(res.mip_dual_bound),gap=float(res.mip_gap),nodes=int(res.mip_node_count)))
            # 最优未证明时仍保留可行候选，不对后级冒称全局优先。
            eps=1e-7 if np.any(c!=1) else 1e-6
            con.append(LinearConstraint(c,res.fun-eps,res.fun+eps))
        for j in np.where(res.x>.5)[0]:
            r=m.route(cand[j]['type'],cand[j]['boxes']);r['id']=f'Q1-{len(tasks)+1:03}';tasks.append(r)
        logs.append(dict(site=site,candidates=n,stages=states))
    summary=dict(sorties=len(tasks),energy=sum(r['energy'] for r in tasks),cumulative_time=sum(r['duration'] for r in tasks),flight_time=sum(r['flight_time'] for r in tasks),delivered=sum(len(r['boxes']) for r in tasks))
    return dict(model=MODEL,reserve=rho,priority=priority,tasks=tasks,solver_log=logs,metrics=summary,scope='Q1忽略时限与实体资源；能耗H1条件结果；不计算并行完工时间')




if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
