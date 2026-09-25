import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from pathlib import Path
import sys,math,json,time
from collections import defaultdict,Counter
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

from dcore import charge,MODEL


def _components(m,tasks):
    sites=sorted(s for s in m.nodes if s!='O01')
    parent={s:s for s in sites}
    def find(s):
        while parent[s]!=s:
            parent[s]=parent[parent[s]];s=parent[s]
        return s
    for task in tasks:
        if not task['order']:
            raise ValueError('运输架次没有服务区')
        for site in task['order']:
            if site not in parent:raise ValueError(f'未知服务区{site}')
            parent[find(site)]=find(task['order'][0])
    groups=defaultdict(list)
    for site in sites:groups[find(site)].append(site)
    return sorted(groups.values(),key=lambda v:v[0])


def _validate_interval(a,b):
    a,b=float(a),float(b)
    if not(math.isfinite(a) and math.isfinite(b))or b<a:
        raise ValueError(f'无效占用区间{a,b}')
    return a,b


def _precompute(m,q3):
    tasks=q3['tasks'];relays=q3['relays'];comps=_components(m,tasks);n=len(comps)
    if not 1<=n<=20:
        raise ValueError('本候选实现限定1至20运输分量；本题至多15')
    names=[x for g in m.types for x in ('drone_'+g,'battery_'+g)]+['relay','component']
    index={name:i for i,name in enumerate(names)};allmask=(1<<n)-1
    masks=np.arange(1<<n,dtype=np.uint32)
    site_index={s:i for i,cc in enumerate(comps)for s in cc}
    task_bits={t['id']:1<<site_index[t['order'][0]]for t in tasks}
    if len(task_bits)!=len(tasks):raise ValueError('运输ID重复')
    relay_masks={r['id']:0 for r in relays}
    if len(relay_masks)!=len(relays):raise ValueError('中继ID重复')
    for row in q3['communication']['intervals']+q3['communication']['boundary_points']:
        # 冻结的备用/guard/direct_else_relay绑定也需要独立资源，不能看mode筛掉。
        relay_id=row.get('relay')
        if relay_id:
            if relay_id not in relay_masks or row['task']not in task_bits:
                raise ValueError('通信记录引用未知任务')
            relay_masks[relay_id] |= task_bits[row['task']]
    unused=[rid for rid,bits in relay_masks.items()if not bits]
    if unused:
        raise ValueError('冻结Q3有未归属任何服务区的中继任务，不能在Q4静默丢弃：'+','.join(unused))
    membership={}
    def belongs(bits):
        if bits not in membership:membership[bits]=(masks&bits)!=0
        return membership[bits]
    intervals={name:[]for name in names}
    transport_work=np.zeros(1<<n);relay_work=np.zeros(1<<n)
    for t in tasks:
        bits=task_bits[t['id']];cc=set(comps[bits.bit_length()-1])
        if not set(t['order'])<=cc:raise ValueError('运输架次跨不同绑定分量')
        a,b=_validate_interval(t['start'],t['return_time']);g=t['type']
        intervals['drone_'+g].append((a,b,bits))
        battery_end=b+charge(t['soc'],m.types[g]['charge_full'])
        intervals['battery_'+g].append((a,battery_end,bits))
        transport_work += float(t['duration'])*belongs(bits)
    for r in relays:
        bits=relay_masks[r['id']]
        a,b=_validate_interval(r['start'],r['entity_ready'])
        _,c=_validate_interval(r['start'],r['component_ready'])
        intervals['relay'].append((a,b,bits));intervals['component'].append((a,c,bits))
        relay_work+=(b-a)*belongs(bits)
    # 每条区间归属某些运输分量；某组子集与之有交集时，完整区间只计一次。
    # 对所有2^n子集同时做半开区间事件扫描，避免为每个子集重排序。
    demand=np.zeros((1<<n,len(names)),dtype=np.int32)
    for name in names:
        events=defaultdict(list)
        for a,b,bits in intervals[name]:
            if a==b:continue
            events[a].append((1,bits));events[b].append((-1,bits))
        active=np.zeros(1<<n,dtype=np.int32);peaks=np.zeros(1<<n,dtype=np.int32)
        for instant in sorted(events):
            # 同时刻结束与开始合并后状态为[t,next_t)，不会双计接触端点。
            for delta,bits in events[instant]:active += delta*belongs(bits)
            if np.any(active<0):raise AssertionError('事件扫描出现负占用')
            np.maximum(peaks,active,out=peaks)
        assert not np.any(active)
        demand[:,index[name]]=peaks
    inventory={**{'drone_'+g:sum(v==g for v in m.drones.values())for g in m.types},**{'battery_'+g:m.types[g]['batteries']for g in m.types},'relay':len(m.relay['drones']),'component':m.relay['components']}
    return dict(comps=comps,n=n,allmask=allmask,names=names,index=index,demand=demand,transport_work=transport_work,relay_work=relay_work,work=transport_work+relay_work,inventory=inventory,task_bits=task_bits,relay_masks=relay_masks)


def _stirling(n,k):
    return sum((-1)**j*math.comb(k,j)*(k-j)**n for j in range(k+1))//math.factorial(k)


def solve(m,q3):
    if q3.get('status')!='independently_validated':
        raise ValueError('Q3尚未独立通过，禁止正式Q4')
    if not q3.get('frozen_sha256'):
        raise ValueError('缺少冻结Q3哈希；调用方仍须核验文件与冻结记录一致')
    begin=time.perf_counter();p=_precompute(m,q3);n=p['n'];full=p['allmask'];names=p['names'];D=p['demand'];W=p['work']
    inv=np.array([p['inventory'][x]for x in names]);base={x:int(D[full,i])for i,x in enumerate(names)}
    entity=[i for i,x in enumerate(names)if x.startswith('drone_')or x=='relay']
    energy=[i for i,x in enumerate(names)if x.startswith('battery_')or x=='component']
    precompute_elapsed=time.perf_counter()-begin
    selected=[];alternatives=[];statistics=[]
    def materialize(k,masks,key,cv):
        groups=[]
        for gi,mask in enumerate(masks,1):
            sites=sorted(s for i,cc in enumerate(p['comps'])if mask&(1<<i)for s in cc)
            tids=sorted(tid for tid,b in p['task_bits'].items()if b&mask)
            rids=[r['id']for r in q3['relays']if p['relay_masks'][r['id']]&mask]
            groups.append(dict(id=f'G{gi}',sites=sites,transport_ids=tids,relay_ids=rids,resources={x:int(D[mask,i])for i,x in enumerate(names)},transport_work=float(p['transport_work'][mask]),relay_work=float(p['relay_work'][mask])))
        total={x:sum(g['resources'][x]for g in groups)for x in names}
        assert all(total[x]>=base[x]for x in names),'非负冗余前提被破坏'
        return dict(K=k,groups=groups,total=total,redundancy={x:total[x]-base[x]for x in names},shortage={x:max(0,total[x]-p['inventory'][x])for x in names},workload_cv=cv,selection_key=list(key),component_masks=list(masks))
    for k in [2,3]:
        if n<k:
            selected.append(dict(K=k,status='structurally_infeasible',groups=[]));statistics.append(dict(K=k,enumerated_partitions=0));continue
        state={'best_key':None,'best_masks':None,'best_cv':None,'balance_key':None,'balance_masks':None,'count':0,'min':None,'max':None,'hist':Counter()}
        def batch(group_masks):
            arrays=[np.asarray(a,dtype=np.int32)for a in group_masks]
            total=sum(D[a]for a in arrays)
            shortage=np.maximum(total-inv,0).sum(axis=1);entities=total[:,entity].sum(axis=1);energies=total[:,energy].sum(axis=1)
            state['count']+=len(total)
            mn=total.min(axis=0);mx=total.max(axis=0)
            state['min']=mn if state['min']is None else np.minimum(state['min'],mn)
            state['max']=mx if state['max']is None else np.maximum(state['max'],mx)
            vals,counts=np.unique(shortage,return_counts=True);state['hist'].update({int(v):int(c)for v,c in zip(vals,counts)})
            # 对照：保持最少库存缺口，改为先均衡，再比较实体和能源数量。
            minimum_shortage=int(shortage.min())
            if state['balance_key'] is None or minimum_shortage<=state['balance_key'][0]:
                ix=np.flatnonzero(shortage==minimum_shortage)
                work_b=np.stack([W[a[ix]] for a in arrays],axis=1);mean_b=work_b.mean(axis=1)
                cv_b=np.divide(np.sqrt(((work_b-mean_b[:,None])**2).mean(axis=1)),mean_b,out=np.zeros(len(ix)),where=mean_b!=0)
                rank=np.lexsort((energies[ix],entities[ix],cv_b));j=int(ix[rank[0]])
                bkey=(minimum_shortage,float(cv_b[rank[0]]),int(entities[j]),int(energies[j]));bmasks=tuple(int(a[j]) for a in arrays)
                if state['balance_key'] is None or (bkey,bmasks)<(state['balance_key'],state['balance_masks']):state['balance_key']=bkey;state['balance_masks']=bmasks
            eligible=np.arange(len(total))
            prefix=[]
            for key in [shortage,entities,energies]:
                value=int(key[eligible].min());prefix.append(value);eligible=eligible[key[eligible]==value]
            if state['best_key']is not None and tuple(prefix)>state['best_key'][:3]:return
            work=np.stack([W[a[eligible]]for a in arrays],axis=1);mean=work.mean(axis=1)
            cv=np.zeros(len(eligible));nonzero=mean!=0
            cv[nonzero]=np.sqrt(((work[nonzero]-mean[nonzero,None])**2).mean(axis=1))/mean[nonzero]
            best_cv=float(cv.min());ties=eligible[cv==best_cv]
            # objective ties get a deterministic smallest canonical component-mask tuple.
            idx=min(ties,key=lambda j:tuple(int(a[j])for a in arrays))
            masks=tuple(int(a[idx])for a in arrays);key=(*prefix,best_cv)
            if state['best_key']is None or (key,masks)<(state['best_key'],state['best_masks']):
                state['best_key']=key;state['best_masks']=masks;state['best_cv']=best_cv if sum(W[a]for a in masks)!=0 else None
        if k==2:
            first=np.arange(1,full,2,dtype=np.int32)
            batch([first,full^first])
        else:
            # 第一组含最小分量0；第二组含剩余最小分量；第三组是补集。
            for first in range(1,full,2):
                rest=full^first
                if rest.bit_count()<2:continue
                anchor=rest&-rest;free=rest^anchor;s=free;seconds=[]
                while s:
                    s=(s-1)&free;seconds.append(anchor|s)
                second=np.array(seconds,dtype=np.int32);third=rest^second
                batch([np.full(len(second),first,dtype=np.int32),second,third])
        expected=_stirling(n,k);assert state['count']==expected,(state['count'],expected)
        best=materialize(k,state['best_masks'],state['best_key'],state['best_cv']);best['enumerated_partitions']=state['count'];selected.append(best)
        bk=state['balance_key'];alt=materialize(k,state['balance_masks'],[bk[0],bk[2],bk[3],bk[1]],bk[1]);alt['alternative_selection_key']=list(bk);alt['selection']='最小库存缺口→工作量CV→实体数→能源件数；对照方案，未替换资源优先结果';alternatives.append(alt)
        statistics.append(dict(K=k,enumerated_partitions=state['count'],expected_stirling_partitions=expected,resource_total_min={x:int(state['min'][i])for i,x in enumerate(names)},resource_total_max={x:int(state['max'][i])for i,x in enumerate(names)},shortage_units_histogram=dict(sorted(state['hist'].items()))))
    return dict(model=q3.get('model',MODEL),source_q3_sha256=q3['frozen_sha256'],assumptions='固定所有任务时刻和通信关系；跨组中继整任务复制；同型可互换并按半开区间重新编号；未用中继必须先澄清归属，不在Q4删除；不暗改Q3',baseline_resources=base,inventory=p['inventory'],components=p['comps'],selected=selected,alternative_selected=alternatives,enumeration_statistics=statistics,subset_precomputation=dict(count_including_empty=1<<n,resource_types=len(names),seconds=precompute_elapsed),elapsed_seconds=time.perf_counter()-begin,all_partitions_retained=False,selection='先库存缺口件数，再实体数、能源件数、工作量CV；条件口径下完全枚举最优，不是Q3/Q4联合全局最优')


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
