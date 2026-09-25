import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import sys
sys.dont_write_bytecode=True
from dcore import *
from communication import clip,xyz,ball_roots,obstruction_intervals,relay_task


def minimum_clearance(terrain,anchor,p0,p1):
    B=np.array([*terrain.grid(*anchor[:2]),anchor[2]])
    A=np.array([*terrain.grid(*p0[:2]),p0[2]])
    Z=np.array([*terrain.grid(*p1[:2]),p1[2]])
    C=A-B;V=Z-A;vertices=np.stack([B,A,Z])
    cols=np.arange(math.ceil(vertices[:,0].min())-1,math.floor(vertices[:,0].max())+1)
    rows=np.arange(math.ceil(vertices[:,1].min())-1,math.floor(vertices[:,1].max())+1)
    if cols.min()<0 or rows.min()<0 or cols.max()>=terrain.a.shape[1] or rows.max()>=terrain.a.shape[0]:raise ValueError('通信三角面超DEM')
    xx,yy=np.meshgrid(cols,rows);candidate=np.ones(xx.shape,dtype=bool)
    for p,q in [(B,A),(A,Z),(Z,B)]:
        nx,ny=-(q[1]-p[1]),q[0]-p[0];vals=vertices[:,0]*nx+vertices[:,1]*ny
        low=nx*xx+ny*yy+min(nx,0)+min(ny,0);high=nx*xx+ny*yy+max(nx,0)+max(ny,0)
        tol=1e-8*(1+abs(nx)+abs(ny));candidate&=(high>=vals.min()-tol)&(low<=vals.max()+tol)
    hs=terrain.a[yy,xx]
    if np.any(hs==-32767) or not np.isfinite(hs).all():raise ValueError('通信范围NoData')
    best=math.inf;critical=None
    for row,col in zip(yy[candidate],xx[candidate]):
        h=float(terrain.a[row,col]);poly=[(0.,0.),(1.,0.),(1.,1.)]
        constraints=[((C[0],V[0]),col+1-B[0]),((-C[0],-V[0]),B[0]-col),((C[1],V[1]),row+1-B[1]),((-C[1],-V[1]),B[1]-row)]
        for coef,k in constraints:
            poly=clip(poly,coef,k)
            if not poly:break
        if poly:
            z=min(B[2]+C[2]*u+V[2]*v-h for u,v in poly)
            if z<best:best=float(z);critical=[int(row),int(col)]
    return best,critical


class Links:
    def __init__(self,m,delta_g_db=0.,clearance_m=0.,legacy_roundoff=False):
        self.m=m;self.delta_g_db=float(delta_g_db);self.clearance_m=float(clearance_m)
        self.tolerance_db=1e-8 if legacy_roundoff else 0.
        # 只更严格地排除贴门槛候选，绝不允许负裕量通过。独立证书仍按原δ/c验收。
        self.selection_budget_guard_db=0. if legacy_roundoff else 1e-9
        self.selection_clearance_guard_m=0. if legacy_roundoff else 1e-7
        assert self.delta_g_db>=0 and self.clearance_m>=0
        assert not legacy_roundoff or (self.delta_g_db==0 and self.clearance_m==0)
        n=m.nodes['O01'];self.gateway=(n['lon'],n['lat'],n['z']+m.comm['gateway_height']);self.cache={}
    def certify(self,anchor,p0,p1,a,b):
        key=(tuple(anchor),tuple(p0),tuple(p1),a,b)
        if key in self.cache:return self.cache[key]
        center=xyz(self.m,anchor);dmax=max(float(np.linalg.norm(xyz(self.m,p)-center)) for p in [p0,p1])
        lim=budget(self.m.comm,a,b);wb=lim-loss(self.m.comm,dmax,True);cl=lim-loss(self.m.comm,dmax,False)
        threshold=self.delta_g_db-self.tolerance_db+self.selection_budget_guard_db
        if wb>=threshold:r=dict(certified=True,method='closed_distance_convexity_full_obstruction',margin_lower_db=wb)
        elif cl<threshold:r=dict(certified=False,method='clear_budget_insufficient',margin_lower_db=cl)
        else:
            c,cell=minimum_clearance(self.m.terrain,anchor,p0,p1)
            r=dict(certified=c>self.clearance_m+self.selection_clearance_guard_m,method='closed_swept_triangle_clearance',margin_lower_db=cl,clearance_lower_m=c,required_clearance_m=self.clearance_m,critical_cell=cell)
        r.update(delta_g_db=self.delta_g_db,budget_roundoff_tolerance_db=self.tolerance_db,selection_budget_guard_db=self.selection_budget_guard_db,selection_clearance_guard_m=self.selection_clearance_guard_m)
        self.cache[key]=r;return r


def point_on(e,t):
    s=(t-e['start'])/(e['end']-e['start']) if e['end']!=e['start'] else 0.
    return (np.array(e['p0'])+(np.array(e['p1'])-e['p0'])*s).tolist()


def regression(m,q):
    links=Links(m,0,0,True);rel={r['id']:r for r in q['relays']};tasks={t['id']:t for t in q['tasks']};bad=[];count=0
    for point,rows in [(False,q['communication']['intervals']),(True,q['communication']['boundary_points'])]:
        for row in rows:
            e=tasks[row['task']]['events'][row['event']];lo=row['time'] if point else row['start'];hi=lo if point else row['end'];p0,p1=point_on(e,lo),point_on(e,hi)
            if row['mode']=='direct':p=links.certify(links.gateway,p0,p1,'T','G')
            else:p=links.certify(rel[row['relay']]['position'],p0,p1,'T','A')
            count+=1
            if not p['certified']:bad.append(dict(row=row,proof=p))
    for r in rel.values():
        p=links.certify(links.gateway,r['position'],r['position'],'R','G')
        if not p['certified']:bad.append(dict(relay=r['id'],proof=p))
    return dict(intervals=len(q['communication']['intervals']),boundaries=len(q['communication']['boundary_points']),checked=count,failures=bad,legacy_roundoff_db=1e-8,delta_g_db=0,clearance_m=0)


def generate(m,q,delta_g_db=.01,clearance_m=1.):
    links=Links(m,delta_g_db,clearance_m);intervals=[];boundaries=[];fail=[];back={};subdivisions=0
    for r in q['relays']:
        back[r['id']]=links.certify(links.gateway,r['position'],r['position'],'R','G')
    # 解析分段用同样DEM+c，仅给候选切点，不作为最终证书。
    class Shifted:
        def __init__(self,t):self.a=np.where(t.a==-32767,t.a,t.a+clearance_m);self.grid=t.grid
    raised=Shifted(m.terrain)
    def cuts_for(anchor,e,a,b):
        x0=xyz(m,e['p0']);x1=xyz(m,e['p1']);z=xyz(m,anchor)
        radius=guaranteed_radius(m.comm,a,b)*10**(-delta_g_db/20)
        cuts=[]
        for rad in [radius,radius*10**(m.comm['obstruction']/20)]:cuts+=ball_roots(x0,x1,z,rad)
        if max(np.linalg.norm(x0-z),np.linalg.norm(x1-z))>radius:
            obs,_=obstruction_intervals(raised,anchor,e['p0'],e['p1']);cuts += [x for pair in obs for x in pair]
        return cuts
    for task in q['tasks']:
        for ei,e in enumerate(task['events']):
            if 'p0' not in e:continue
            D=e['end']-e['start'];cuts=[e['start'],e['end']]
            options=[r for r in q['relays'] if back[r['id']]['certified'] and r['service_start']<=e['end'] and r['service_end']>=e['start']]
            cuts += [e['start']+D*x for x in cuts_for(links.gateway,e,'T','G')]
            for r in options:
                cuts += [e['start']+D*x for x in cuts_for(r['position'],e,'T','A')]
                cuts += [x for x in [r['ready'],r['service_start'],r['service_end']] if e['start']<x<e['end']]
            cuts=sorted(set(cuts))
            def choose(lo,hi):
                p0,p1=point_on(e,lo),point_on(e,hi)
                direct=links.certify(links.gateway,p0,p1,'T','G')
                if direct['certified']:return 'direct','',direct
                feasible=[]
                for r in options:
                    if r['service_start']<=lo and r['ready']<=lo and hi<=r['service_end']:
                        pr=links.certify(r['position'],p0,p1,'T','A')
                        if pr['certified']:feasible.append((min(pr['margin_lower_db'],back[r['id']]['margin_lower_db']),r['id'],pr))
                if feasible:
                    _,rid,pr=max(feasible,key=lambda x:(x[0],x[1]));return 'direct_else_relay',rid,pr
                return 'outage','',direct
            rows=[]
            def cover(lo,hi,depth=0):
                nonlocal subdivisions
                mode,rid,proof=choose(lo,hi)
                if mode=='outage' and depth<28 and hi-lo>1e-9:
                    subdivisions+=1;mid=(lo+hi)/2;cover(lo,mid,depth+1);cover(mid,hi,depth+1);return
                row=dict(task=task['id'],event=ei,phase=e['phase'],start=lo,end=hi,mode=mode,relay=rid,interval='closed certificate; boundary policy explicit',certificate=proof)
                rows.append(row)
                if mode=='outage':fail.append(row)
            for lo,hi in zip(cuts,cuts[1:]):
                if hi>lo:cover(lo,hi)
            intervals+=rows
            for tm in sorted({x for row in rows for x in [row['start'],row['end']]}):
                mode,rid,proof=choose(tm,tm);row=dict(task=task['id'],event=ei,time=tm,mode=mode,relay=rid,certificate=proof);boundaries.append(row)
                if mode=='outage':fail.append(row)
    margins=[r['certificate']['margin_lower_db'] for r in intervals+boundaries if r['mode']!='outage']+[p['margin_lower_db'] for p in back.values()]
    return dict(policy='direct_first_else_bound_relay',method='analytic candidate cuts plus closed swept-triangle certificates',delta_g_db=delta_g_db,clearance_m=clearance_m,budget_roundoff_tolerance_db=0,artificial_guard_windows=False,proof_bisections=subdivisions,intervals=intervals,boundary_points=boundaries,failures=fail,backhaul_certificates=back,min_certified_margin_db=min(margins))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
