import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Independent Q4 audit. Does not import formal solver or communication modules.
from pathlib import Path
from collections import defaultdict, Counter
import argparse, hashlib, heapq, json, math, time
import numpy as np
import openpyxl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT/'data/original/数据/无人机应急物资运输基础数据'
RES = ['drone_A','drone_B','drone_C','battery_A','battery_B','battery_C','relay','component']
ENTITY = [0,1,2,6]
ENERGY = [3,4,5,7]

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')

def raw_inputs():
    values = {}
    files = ['调度中心与服务区.xlsx','运输无人机数据.xlsx','中继无人机数据.xlsx']
    for name in files:
        wb=openpyxl.load_workbook(DATA/name,read_only=True,data_only=True)
        values[name]=list(wb['数据'].values);wb.close()
    nodes=values[files[0]]
    sites=sorted(row[0] for row in nodes[6:21])
    tr=values[files[1]]
    fleet=Counter(row[1] for row in tr[8:16])
    batteries={row[0]:int(row[1]) for row in tr[19:22]}
    full_charge={row[0]:float(row[2]) for row in tr[19:22]}
    rr=values[files[2]]
    inv=[fleet['A'],fleet['B'],fleet['C'],batteries['A'],batteries['B'],batteries['C'],sum(row[0] is not None for row in rr[6:8]),int(rr[11][1])]
    return dict(sites=sites,inventory=np.asarray(inv,dtype=np.int32),charge=full_charge,
                relay_turn=float(rr[2][11]),relay_charge=float(rr[11][2]),
                files={name:sha(DATA/name) for name in files})

def charging(soc,total):
    assert 0<=soc<=1
    # Fix the shared floating-point formula convention at zero-slack handoffs.
    # Algebraic reassociation differs by 4.55e-13 s in old v003 (documented).
    # This is still independently implemented from original charge stages.
    if soc>=.9:return total*.35*(1-soc)/.1
    return total*(.65*(.9-soc)/.9+.35)

def components(sites, memberships):
    sets=[{s} for s in sites]
    for members in memberships:
        members=set(members)
        assert members and members<=set(sites)
        merged=members.copy();keep=[]
        for part in sets:
            if part & members:merged |= part
            else:keep.append(part)
        sets=keep+[merged]
    return sorted([sorted(v) for v in sets])

def context(q,raw):
    sites=raw['sites'];si={s:i for i,s in enumerate(sites)}
    tasks={t['id']:t for t in q['tasks']};relays={r['id']:r for r in q['relays']}
    assert len(tasks)==len(q['tasks']) and len(relays)==len(q['relays'])
    tmask={tid:sum(1<<si[s] for s in set(t['order'])) for tid,t in tasks.items()}
    bound={rid:set() for rid in relays};rows=q['communication']['intervals']+q['communication']['boundary_points']
    by_task=defaultdict(set)
    for row in rows:
        assert row['task'] in tasks
        if row.get('relay'):
            rid=row['relay'];assert rid in relays
            bound[rid].update(tasks[row['task']]['order']);by_task[row['task']].add(rid)
    assert all(bound.values()),'Every frozen relay task must retain at least one attribution.'
    rmask={rid:sum(1<<si[s] for s in ss) for rid,ss in bound.items()}
    iv={res:[] for res in RES};tw=[];rw=[];derived=[]
    for tid,t in tasks.items():
        a=float(t['start']);b=float(t['return_time']);g=t['type'];assert b>a
        iv['drone_'+g].append((a,b,tmask[tid],tid,t['drone']))
        end=b+charging(float(t['soc']),raw['charge'][g])
        iv['battery_'+g].append((a,end,tmask[tid],tid,t['battery']))
        tw.append((b-a,tmask[tid]))
        assert abs((b-a)-float(t['duration']))<1e-8
    for rid,r in relays.items():
        a=float(r['start']);b=float(r['return_time'])+raw['relay_turn']
        c=b+charging(float(r['soc']),raw['relay_charge']);assert c>=b>a
        derived.append(dict(id=rid,entity_ready=b,component_ready=c,
                            matches_frozen=(abs(b-float(r['entity_ready']))<1e-8 and abs(c-float(r['component_ready']))<1e-8)))
        iv['relay'].append((a,b,rmask[rid],rid,r['drone']))
        iv['component'].append((a,c,rmask[rid],rid,r['component']))
        rw.append((b-a,rmask[rid]))
    assert all(x['matches_frozen'] for x in derived)
    # Literal global-ID constraints are a separate, stronger interpretation.
    id_members=defaultdict(set)
    for res,items in iv.items():
        for _,_,mask,_,label in items:
            id_members[res+'/'+label].update(s for s,i in si.items() if mask>>i&1)
    return dict(sites=sites,si=si,tasks=tasks,relays=relays,tmask=tmask,rmask=rmask,
                bindings=bound,rows=len(rows),intervals=iv,transport_work=tw,relay_work=rw,
                derived_relay_times=derived,
                literal_global_id_components=components(sites,id_members.values()),
                copy_components=components(sites,[t['order'] for t in tasks.values()]),
                no_copy_components=components(sites,[t['order'] for t in tasks.values()]+list(bound.values())))

def precompute(ctx):
    count=1<<len(ctx['sites']);masks=np.arange(count,dtype=np.uint32)
    demand=np.zeros((count,len(RES)),dtype=np.int32)
    for j,res in enumerate(RES):
        events=[]
        for a,b,mask,tid,label in ctx['intervals'][res]:
            events.extend([(a,1,mask),(b,-1,mask)])
        active=np.zeros(count,dtype=np.int32)
        # For half-open occupancy, a release is processed before a same-time start.
        for instant,delta,mask in sorted(events):
            active+=delta*((masks&mask)!=0)
            assert np.all(active>=0)
            demand[:,j]=np.maximum(demand[:,j],active)
        assert np.all(active==0)
    workloads=[]
    for terms in [ctx['transport_work'],ctx['relay_work']]:
        arr=np.zeros(count)
        for duration,mask in terms:arr+=duration*((masks&mask)!=0)
        workloads.append(arr)
    return demand,workloads

def stirling(n,k):
    table=[[0]*(k+1) for _ in range(n+1)];table[0][0]=1
    for i in range(1,n+1):
        for j in range(1,min(k,i)+1):table[i][j]=j*table[i-1][j]+table[i-1][j-1]
    return table[n][k]

def partition_batches(blocks,si,k,batchsize=8192):
    """Base-k labels, reduced to restricted-growth strings (different enumeration).

    Block 0 has label 0; first occurrence of label 1 must precede label 2.
    Every accepted labelling represents exactly one unordered nonempty partition.
    """
    n=len(blocks)
    if n<k:return
    bm=[sum(1<<si[s] for s in block) for block in blocks]
    for offset in range(0,k**(n-1),batchsize):
        code=np.arange(offset,min(offset+batchsize,k**(n-1)),dtype=np.int64)
        labels=code.copy();groups=np.zeros((len(code),k),dtype=np.uint32);groups[:,0]=bm[0]
        seen1=np.zeros(len(code),dtype=bool);ok=np.ones(len(code),dtype=bool)
        for blockmask in bm[1:]:
            digit=labels%k;labels//=k
            if k==3:
                ok &= ~((digit==2)&~seen1)
                seen1 |= digit==1
            for group in range(k):groups[:,group] |= np.where(digit==group,blockmask,0).astype(np.uint32)
        ok &= np.all(groups!=0,axis=1)
        if np.any(ok):yield groups[ok]

def colour(items,group_mask,res,prefix):
    selected=sorted((a,b,tid,label) for a,b,mask,tid,label in items if mask&group_mask)
    busy=[];free=[];n=0;assignment=[]
    for a,b,tid,label in selected:
        while busy and busy[0][0]<=a:
            _,number=heapq.heappop(busy);heapq.heappush(free,number)
        if free:number=heapq.heappop(free)
        else:n+=1;number=n
        heapq.heappush(busy,(b,number))
        assignment.append(dict(task=tid,resource=f'{prefix}/{res}/{number:02d}',start=a,end=b,source_label=label))
    tracks=defaultdict(list)
    for item in assignment:tracks[item['resource']].append(item)
    assert all(all(left['end']<=right['start'] for left,right in zip(rows,rows[1:])) for rows in tracks.values())
    return n,assignment

def materialize(ctx,raw,D,works,parts,key,selection):
    groups=[];allassign=[]
    for i,mask in enumerate(parts,1):
        gname=f'G{i}';need={};assignment=[]
        for j,res in enumerate(RES):
            n,colouring=colour(ctx['intervals'][res],mask,res,gname)
            assert n==int(D[mask,j]);need[res]=n;assignment.extend(colouring)
        group=dict(id=gname,sites=[s for s in ctx['sites'] if mask>>ctx['si'][s]&1],
                   transport_ids=sorted(tid for tid,m in ctx['tmask'].items() if m&mask),
                   relay_ids=sorted(rid for rid,m in ctx['rmask'].items() if m&mask),
                   resources=need,transport_work=float(works[0][mask]),relay_work=float(works[1][mask]))
        groups.append(group);allassign.extend(assignment)
    total=np.sum([D[m] for m in parts],axis=0)
    work=np.array([works[0][m]+works[1][m] for m in parts]);cv=float(work.std()/work.mean())
    result=dict(K=len(parts),groups=groups,total=dict(zip(RES,map(int,total))),
                shortage=dict(zip(RES,map(int,np.maximum(total-raw['inventory'],0)))),
                redundancy=dict(zip(RES,map(int,total-D[-1]))),workload_cv=cv,
                selection=selection,selection_key=list(key),site_masks=list(parts),
                constructive_colouring=allassign,colouring_pass=True,
                relay_task_copies=sum(len(g['relay_ids']) for g in groups))
    # Every frozen backup relation is inherited in the unique transport group.
    ownership={tid:g for g in groups for tid in g['transport_ids']}
    assert len(ownership)==len(ctx['tasks'])
    assert Counter(tid for g in groups for tid in g['transport_ids'])==Counter({tid:1 for tid in ctx['tasks']})
    assert Counter(s for g in groups for s in g['sites'])==Counter({s:1 for s in ctx['sites']})
    for rid,sites in ctx['bindings'].items():
        for tid,t in ctx['tasks'].items():
            if rid in ctx['rmask'] and ctx['tmask'][tid]&ctx['rmask'][rid]:
                assert rid in ownership[tid]['relay_ids']
    result['all_frozen_bindings_retained']=True
    return result

def enumerate_rule(ctx,raw,D,works,blocks):
    work=works[0]+works[1];answer=[];balance=[];stats=[]
    for k in [2,3]:
        best=None;bal=None;count=0;hist=Counter();minimum=None;maximum=None
        for gs in partition_batches(blocks,ctx['si'],k):
            total=np.sum(D[gs],axis=1)
            short=np.maximum(total-raw['inventory'],0).sum(axis=1)
            en=total[:,ENTITY].sum(axis=1);bat=total[:,ENERGY].sum(axis=1)
            w=work[gs];cv=w.std(axis=1)/w.mean(axis=1)
            # Keep deterministic canonical masks after all numeric objectives.
            lexical=tuple(gs[:,j] for j in range(k-1,-1,-1))
            idx=int(np.lexsort((*lexical,cv,bat,en,short))[0])
            candidate=((int(short[idx]),int(en[idx]),int(bat[idx]),float(cv[idx])),tuple(map(int,gs[idx])))
            if best is None or candidate<best:best=candidate
            idx=int(np.lexsort((*lexical,bat,en,cv,short))[0])
            candidate=((int(short[idx]),float(cv[idx]),int(en[idx]),int(bat[idx])),tuple(map(int,gs[idx])))
            if bal is None or candidate<bal:bal=candidate
            count+=len(gs);vals,nums=np.unique(short,return_counts=True)
            hist.update({int(v):int(num) for v,num in zip(vals,nums)})
            mn=total.min(axis=0);mx=total.max(axis=0)
            minimum=mn if minimum is None else np.minimum(minimum,mn)
            maximum=mx if maximum is None else np.maximum(maximum,mx)
        expected=stirling(len(blocks),k);assert count==expected,(count,expected)
        if best is None:
            answer.append(dict(K=k,status='structurally_infeasible',groups=[]))
            balance.append(dict(K=k,status='structurally_infeasible',groups=[]))
        else:
            answer.append(materialize(ctx,raw,D,works,best[1],best[0],'shortage,entities,energy_units,CV'))
            balance.append(materialize(ctx,raw,D,works,bal[1],bal[0],'shortage,CV,entities,energy_units'))
        stats.append(dict(K=k,enumerated_partitions=count,expected_stirling_partitions=expected,
                          shortage_histogram=dict(sorted(hist.items())),
                          resource_total_min=None if minimum is None else dict(zip(RES,map(int,minimum))),
                          resource_total_max=None if maximum is None else dict(zip(RES,map(int,maximum)))))
    return dict(components=blocks,selected=answer,alternative_selected=balance,enumeration_statistics=stats)

def compare(formal,independent):
    checks=[]
    assert len(formal['selected'])==len(independent['selected'])==2
    assert len(formal['alternative_selected'])==len(independent['alternative_selected'])==2
    for listname in ['selected','alternative_selected']:
        for f,g in zip(formal[listname],independent[listname]):
            fields={key:f[key]==g[key] for key in ['K','total','shortage','redundancy']}
            fields['cv']=abs(f['workload_cv']-g['workload_cv'])<=1e-11
            fields['groups']=sorted(tuple(x['sites']) for x in f['groups'])==sorted(tuple(x['sites']) for x in g['groups'])
            independent_groups={tuple(sorted(x['sites'])):x for x in g['groups']}
            per_group=[]
            for group in f['groups']:
                same=independent_groups.get(tuple(sorted(group['sites'])))
                if same is None:per_group.append(False);continue
                per_group.append(group['resources']==same['resources'] and
                                 sorted(group['transport_ids'])==same['transport_ids'] and
                                 sorted(group['relay_ids'])==same['relay_ids'] and
                                 abs(group['transport_work']-same['transport_work'])<=1e-8 and
                                 abs(group['relay_work']-same['relay_work'])<=1e-8)
            fields['per_group_resources_tasks_workload']=all(per_group)
            checks.append(dict(K=f['K'],selection=listname,checks=fields,pass_=all(fields.values())))
    stats=[]
    for official,own in zip(formal['enumeration_statistics'],independent['enumeration_statistics']):
        exact=['K','enumerated_partitions','expected_stirling_partitions','resource_total_min','resource_total_max']
        fields={key:official[key]==own[key] for key in exact}
        fields['full_shortage_histogram']={str(k):v for k,v in official['shortage_units_histogram'].items()}=={str(k):v for k,v in own['shortage_histogram'].items()}
        stats.append(dict(K=official['K'],checks=fields,pass_=all(fields.values())))
    comps=sorted(formal['components'])==sorted(independent['components'])
    return dict(passed=comps and all(c['pass_'] for c in checks+stats),components_match=comps,details=checks,enumeration_statistics=stats)

def selftest():
    # Two intervals touching at t=2 share a resource; a genuine overlap needs 2.
    items=[(0.,2.,1,'a','x'),(2.,4.,1,'b','y'),(1.,3.,2,'c','z')]
    assert colour(items,1,'test','G')[0]==1
    assert colour(items,3,'test','G')[0]==2
    for n in range(2,8):
        blocks=[[str(i)] for i in range(n)];si={str(i):i for i in range(n)}
        for k in [2,3]:
            rows=[tuple(map(int,row)) for batch in partition_batches(blocks,si,k,17) for row in batch]
            assert len(rows)==len(set(rows))==stirling(n,k)
            assert all(sum(r)==(1<<n)-1 for r in rows)
    assert charging(1.,100.)==0 and abs(charging(0.,100.)-100)<1e-12
    assert components(['a','b','c'],[['a','b'],['b','c']])==[['a','b','c']]
    return dict(passed=True,scope='half-open colouring; independent restricted-growth enumeration n=2..7; charge endpoints; transitive membership')



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
