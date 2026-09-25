import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import sys
sys.dont_write_bytecode=True
from dcore import *
from communication_v003_1 import Links,point_on
from fractions import Fraction as F
from decimal import Decimal as D,localcontext
from collections import defaultdict

def frac(x):return F(str(x))
def dec(x):return D(x.numerator)/D(x.denominator) if isinstance(x,F) else D(str(x))

def exact_clip(poly,a,b,c):
    if not poly:return []
    out=[];prev=poly[-1];vp=c-a*prev[0]-b*prev[1]
    for cur in poly:
        vc=c-a*cur[0]-b*cur[1]
        if (vp>=0)!=(vc>=0):
            t=vp/(vp-vc);out.append((prev[0]+t*(cur[0]-prev[0]),prev[1]+t*(cur[1]-prev[1])))
        if vc>=0:out.append(cur)
        prev=cur;vp=vc
    return out


def shadows(m,anchor,p0,p1):
    B0=np.array([*m.terrain.grid(*anchor[:2]),anchor[2]])
    A0=np.array([*m.terrain.grid(*p0[:2]),p0[2]])
    Z0=np.array([*m.terrain.grid(*p1[:2]),p1[2]])
    vertices=np.stack([B0,A0,Z0])
    cols=np.arange(math.ceil(vertices[:,0].min())-1,math.floor(vertices[:,0].max())+1)
    rows=np.arange(math.ceil(vertices[:,1].min())-1,math.floor(vertices[:,1].max())+1)
    xx,yy=np.meshgrid(cols,rows);mask=np.ones(xx.shape,dtype=bool)
    for p,q in [(B0,A0),(A0,Z0),(Z0,B0)]:
        nx,ny=-(q[1]-p[1]),q[0]-p[0];vals=vertices[:,0]*nx+vertices[:,1]*ny
        low=nx*xx+ny*yy+min(nx,0)+min(ny,0);high=nx*xx+ny*yy+max(nx,0)+max(ny,0)
        tol=1e-8*(1+abs(nx)+abs(ny));mask&=(high>=vals.min()-tol)&(low<=vals.max()+tol)
    mask &= m.terrain.a[yy,xx]>=vertices[:,2].min()-1e-8
    B=list(map(frac,B0));A=list(map(frac,A0));Z=list(map(frac,Z0));C=[a-b for a,b in zip(A,B)];V=[z-a for z,a in zip(Z,A)]
    iv=[]
    for row,col in zip(yy[mask],xx[mask]):
        h=frac(float(m.terrain.a[row,col]));cons=[(C[0],V[0],F(int(col)+1)-B[0]),(-C[0],-V[0],B[0]-int(col)),(C[1],V[1],F(int(row)+1)-B[1]),(-C[1],-V[1],B[1]-int(row)),(C[2],V[2],h-B[2])]
        poly=[(F(0),F(0)),(F(1),F(0)),(F(1),F(1))]
        for a,b,c in cons:
            poly=exact_clip(poly,a,b,c)
            if not poly:break
        if not poly:continue
        if any(u==0 for u,v in poly):return [(F(0),F(1))],dict(B=list(map(str,B)),A=list(map(str,A)),Z=list(map(str,Z)))
        ts=[v/u for u,v in poly];iv.append((min(ts),max(ts)))
    merged=[]
    for lo,hi in sorted(iv):
        if merged and lo<=merged[-1][1]:merged[-1][1]=max(hi,merged[-1][1])
        else:merged.append([lo,hi])
    return merged,dict(B=list(map(str,B)),A=list(map(str,A)),Z=list(map(str,Z)))


class Nominal:
    def __init__(self,m):
        self.m=m;self.gateway=Links(m).gateway;self.cache={}
    def profile(self,p0,p1):
        key=(tuple(p0),tuple(p1))
        if key in self.cache:return self.cache[key]
        m=self.m;B=[dec(float(x)) for x in [*m.terrain.xy(*self.gateway[:2]),self.gateway[2]]]
        X0=[dec(float(x)) for x in [*m.terrain.xy(*p0[:2]),p0[2]]];X1=[dec(float(x)) for x in [*m.terrain.xy(*p1[:2]),p1[2]]]
        v=[b-a for a,b in zip(X0,X1)];w=[a-b for a,b in zip(X0,B)]
        aa=sum(x*x for x in v);bb=2*sum(x*y for x,y in zip(w,v));cc=sum(x*x for x in w)
        lim=dec(budget(m.comm,'T','G'));r_clear=D(1000)*(D(10)**((lim-D('32.45')-20*dec(m.comm['f']).log10())/20));r_block=r_clear/(D(10)**(dec(m.comm['obstruction'])/20))
        cuts={D(0):{'event'},D(1):{'event'}}
        def add(t,kind):
            if 0<=t<=1:cuts.setdefault(t,set()).add(kind)
        for r,name in [(r_block,'blocked_radius'),(r_clear,'clear_radius')]:
            disc=bb*bb-4*aa*(cc-r*r)
            if aa>0 and disc>=0:
                for t in [(-bb-disc.sqrt())/(2*aa),(-bb+disc.sqrt())/(2*aa)]:add(t,name)
        guaranteed=max(cc,aa+bb+cc)<=r_block*r_block
        if guaranteed:obs=[];basis={}
        else:
            obs,basis=shadows(m,self.gateway,p0,p1)
            for lo,hi in obs:add(dec(lo),'shadow');add(dec(hi),'shadow')
        result=dict(cuts=cuts,obs=obs,aa=aa,bb=bb,cc=cc,r_clear=r_clear,r_block=r_block,basis=basis,xyz_basis=[list(map(str,B)),list(map(str,X0)),list(map(str,X1))])
        self.cache[key]=result;return result
    @staticmethod
    def available(pr,t,boundary=False):
        blocked=any(dec(lo)<=t<=dec(hi) for lo,hi in pr['obs'])
        r=pr['r_block'] if blocked else pr['r_clear']
        if boundary:
            tags=pr['cuts'].get(t,set())
            if ('blocked_radius' if blocked else 'clear_radius') in tags:return True
        return pr['aa']*t*t+pr['bb']*t+pr['cc']<=r*r


def build(m,q):
    nominal=Nominal(m);robust=Links(m,.01,1);relays={r['id']:r for r in q['relays']};by=defaultdict(list)
    for r in q['communication']['intervals']:by[r['task'],r['event']].append(r)
    records=[];points=[];sources=[];fail=[]
    for task in q['tasks']:
        for ei,e in enumerate(task['events']):
            if 'p0' not in e:continue
            pr=nominal.profile(e['p0'],e['p1']);start=dec(e['start']);duration=dec(e['end'])-start
            proofrows=by[task['id'],ei];cuts=set(pr['cuts'])
            for r in proofrows:
                cuts|={(dec(r['start'])-start)/duration,(dec(r['end'])-start)/duration}
            cuts=sorted(t for t in cuts if 0<=t<=1)
            source_id=len(sources)
            sources.append(dict(id=source_id,task=task['id'],event=ei,shadow_rational=[[str(a),str(b)] for a,b in pr['obs']],polynomial=[str(pr[k]) for k in ['aa','bb','cc']],radii=[str(pr['r_block']),str(pr['r_clear'])],pixel_basis=pr['basis'],xyz_basis=pr['xyz_basis'],critical_parameters=[dict(t=str(t),kinds=sorted(tags)) for t,tags in sorted(pr['cuts'].items())]))
            def binding(lo,hi):
                # 使用已冻结候选中存在的备用关系；不在展示层引入新中继。
                ridset={r['relay'] for r in proofrows if r['relay'] and r['start']<=lo<=r['end'] and r['start']<=hi<=r['end']}
                choices=[]
                for rid in sorted(ridset):
                    r=relays[rid]
                    p=robust.certify(r['position'],point_on(e,lo),point_on(e,hi),'T','A')
                    if r['ready']<=lo and r['service_start']<=lo and hi<=r['service_end'] and p['certified']:choices.append((p['margin_lower_db'],rid,p))
                return max(choices,key=lambda x:(x[0],x[1])) if choices else None
            for lo,hi in zip(cuts,cuts[1:]):
                a,b=start+duration*lo,start+duration*hi;fa,fb=float(a),float(b)
                mode='direct' if nominal.available(pr,(lo+hi)/2) else 'relay';rid='';proof=None
                if mode=='relay':
                    found=binding(fa,fb)
                    if found:_,rid,proof=found
                    else:fail.append(dict(reason='no_inherited_robust_relay',task=task['id'],event=ei,start=fa,end=fb))
                if fa==fb:
                    fail.append(dict(reason='distinct_exact_times_collapse_in_Excel_binary64',task=task['id'],start_exact=str(a),end_exact=str(b)))
                records.append(dict(task=task['id'],event=ei,phase=e['phase'],start=fa,end=fb,start_exact_decimal=str(a),end_exact_decimal=str(b),parameter_start=str(lo),parameter_end=str(hi),mode=mode,relay=rid,nominal_profile=source_id,endpoint_semantics='open; exact instants in boundary supplement',robust_relay_certificate=proof))
            for t in cuts:
                a=start+duration*t;fa=float(a);mode='direct' if nominal.available(pr,t,True) else 'relay';rid=''
                if mode=='relay':
                    found=binding(fa,fa)
                    if found:_,rid,_=found
                    else:fail.append(dict(reason='boundary_no_inherited_relay',task=task['id'],event=ei,time=fa))
                points.append(dict(task=task['id'],event=ei,time=fa,time_exact_decimal=str(a),parameter=str(t),mode=mode,relay=rid,nominal_profile=source_id))
    # 相邻事件共享同一物理瞬时：保留逐事件审计行，但统一唯一提供者。
    # 只在同任务、同精确时刻、同位置的事件间继承既有备用关系，不新增绑定。
    grouped=defaultdict(list);tasks={t['id']:t for t in q['tasks']}
    for p in points:grouped[p['task'],D(p['time_exact_decimal'])].append(p)
    for (tid,exact),group in grouped.items():
        if len({p['mode'] for p in group})!=1:
            fail.append(dict(reason='adjacent_nominal_mode_conflict',task=tid,time_exact=str(exact)));continue
        if group[0]['mode']=='direct':continue
        positions=[point_on(tasks[tid]['events'][p['event']],p['time']) for p in group]
        if any(tuple(x)!=tuple(positions[0]) for x in positions[1:]):
            fail.append(dict(reason='adjacent_position_conflict',task=tid,time_exact=str(exact)));continue
        time=float(exact);origins=defaultdict(list)
        for p in group:
            for row in by[tid,p['event']]:
                if row['relay'] and row['start']<=time<=row['end']:origins[row['relay']].append(p['event'])
        choices=[]
        for rid,events in origins.items():
            r=relays[rid];proof=robust.certify(r['position'],positions[0],positions[0],'T','A')
            if r['ready']<=time and r['service_start']<=time<=r['service_end'] and proof['certified']:
                choices.append((proof['margin_lower_db'],rid,sorted(set(events))))
        if not choices:
            fail.append(dict(reason='unified_boundary_no_inherited_relay',task=tid,time_exact=str(exact)));continue
        _,rid,events=max(choices,key=lambda x:(x[0],x[1]))
        for p in group:p.update(relay=rid,binding_source_events=events)
    return dict(delta_db=0,clearance_m=0,precision_decimal_digits=80,intervals=records,boundary_points=points,analytic_profiles=sources,failures=fail,semantics='Open intervals from all nominal analytic switches and robust-certificate boundaries. Boundaries listed separately; radius equality available, terrain contact blocked. Decimal serialized endpoint constants define numeric geometry; no fixed guard window or negative budget tolerance. Adjacent-event boundary audit rows share one physical provider, inherited only from existing same-task same-position adjacent-event bindings.')



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
