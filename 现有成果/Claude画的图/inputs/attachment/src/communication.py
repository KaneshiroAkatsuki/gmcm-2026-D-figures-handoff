import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dcore import *

def clip(poly,coef,constant):
    """uv凸多边形与 coef@uv <= constant 相交；不按xyz去重。"""
    if not poly:return []
    out=[];prev=poly[-1];dp=constant-coef[0]*prev[0]-coef[1]*prev[1]
    for cur in poly:
        dc=constant-coef[0]*cur[0]-coef[1]*cur[1]
        pin=dp>=-1e-10;cin=dc>=-1e-10
        if pin!=cin:
            t=dp/(dp-dc);out.append((prev[0]+t*(cur[0]-prev[0]),prev[1]+t*(cur[1]-prev[1])))
        if cin:out.append(cur)
        prev=cur;dp=dc
    return out

def merge_intervals(intervals):
    out=[]
    for lo,hi in sorted(intervals):
        lo=max(0.,float(lo));hi=min(1.,float(hi))
        if lo>hi+1e-12:continue
        if out and lo<=out[-1][1]+1e-12:out[-1][1]=max(out[-1][1],hi)
        else:out.append([lo,hi])
    return out

def obstruction_intervals(terrain,anchor,a0,a1):
    """所有视线 B+u(A0-B)+v(A1-A0), 0<=v<=u<=1, t=v/u。"""
    B=np.array([*terrain.grid(*anchor[:2]),anchor[2]])
    A=np.array([*terrain.grid(*a0[:2]),a0[2]])
    Z=np.array([*terrain.grid(*a1[:2]),a1[2]])
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
    candidate&=hs>=vertices[:,2].min()-1e-8
    intervals=[];count=0
    for row,col in zip(yy[candidate],xx[candidate]):
        h=float(terrain.a[row,col]);poly=[(0.,0.),(1.,0.),(1.,1.)]
        constraints=[((C[0],V[0]),col+1-B[0]),((-C[0],-V[0]),B[0]-col),((C[1],V[1]),row+1-B[1]),((-C[1],-V[1]),B[1]-row),((C[2],V[2]),h-B[2])]
        for coef,k in constraints:
            poly=clip(poly,coef,k)
            if not poly:break
        if not poly:continue
        count+=1
        if col-1e-10<=B[0]<=col+1+1e-10 and row-1e-10<=B[1]<=row+1+1e-10 and B[2]<=h+1e-10:return [[0.,1.]],count
        ratios=[v/u for u,v in poly if u>1e-12]
        if ratios:intervals.append((min(ratios),max(ratios)))
    return merge_intervals(intervals),count

def xyz(m,p):return np.array([*m.terrain.xy(p[0],p[1]),p[2]],dtype=float)

def ball_roots(x0,x1,anchor,radius):
    d=x0-anchor;v=x1-x0;aa=float(v@v);bb=float(2*d@v);cc=float(d@d-radius**2)
    if aa<1e-20:return []
    disc=bb*bb-4*aa*cc
    if disc<-1e-6:return []
    disc=max(0,disc);root=math.sqrt(disc)
    return [max(0.,min(1.,v)) for v in [(-bb-root)/(2*aa),(-bb+root)/(2*aa)] if -1e-12<=v<=1+1e-12]

class LinkProfile:
    def __init__(self,m,anchor,p0,p1,a,b):
        self.m=m;self.anchor=anchor;self.p0=p0;self.p1=p1;self.limit=budget(m.comm,a,b)
        self.x0=xyz(m,p0);self.x1=xyz(m,p1);self.z=xyz(m,anchor)
        r=guaranteed_radius(m.comm,a,b);self.worst_guaranteed=max(np.linalg.norm(self.x0-self.z),np.linalg.norm(self.x1-self.z))<=r-1e-7
        self.blocked=[];self.intersections=0
        if not self.worst_guaranteed:self.blocked,self.intersections=obstruction_intervals(m.terrain,anchor,p0,p1)
        self.cuts=[0.,1.]+[t for lohi in self.blocked for t in lohi]
        for radius in [r,r*10**(m.comm['obstruction']/20)]:self.cuts+=ball_roots(self.x0,self.x1,self.z,radius)
        self.cuts=sorted(set(self.cuts))
    def available(self,t):return bool(self.margin(t)>=-1e-8)
    def blocked_at(self,t):return self.worst_guaranteed or any(lo-1e-12<=t<=hi+1e-12 for lo,hi in self.blocked)
    def margin(self,t):
        d=float(np.linalg.norm(self.x0+(self.x1-self.x0)*t-self.z))
        return self.limit-loss(self.m.comm,d,self.blocked_at(t))
    def status_intervals(self):
        return [(lo,hi,self.available((lo+hi)/2)) for lo,hi in zip(self.cuts[:-1],self.cuts[1:])]

class Communications:
    def __init__(self,m):
        self.m=m;n=m.nodes['O01'];self.gateway=(n['lon'],n['lat'],n['z']+m.comm['gateway_height']);self.cache={}
    def profile(self,anchor,p0,p1,a,b):
        key=(tuple(anchor),tuple(p0),tuple(p1),a,b)
        if key not in self.cache:self.cache[key]=LinkProfile(self.m,anchor,p0,p1,a,b)
        return self.cache[key]
    def direct_gaps(self,tasks):
        gaps=[];points=[]
        for task in tasks:
            for index,e in enumerate(task['events']):
                if 'p0' not in e:continue
                pr=self.profile(self.gateway,e['p0'],e['p1'],'T','G')
                for lo,hi,available in pr.status_intervals():
                    if not available:gaps.append(dict(task=task['id'],event=index,lo=lo,hi=hi,start=e['start']+lo*(e['end']-e['start']),end=e['start']+hi*(e['end']-e['start']),phase=e['phase']))
                for t in pr.cuts:
                    if not pr.available(t):points.append(dict(task=task['id'],event=index,t=t,time=e['start']+t*(e['end']-e['start'])))
        return gaps,points
    def verify_plan(self,tasks,relays):
        records=[];endpoints=[];fail=[];minmargin=math.inf
        back={}
        for r in relays:
            if 'ready' in r and r['service_start'] < r['ready']-1e-8:
                raise ValueError('中继建链完成前服务: '+r['id'])
            p=r['position'];back[r['id']]=self.profile(self.gateway,p,p,'R','G').available(0)
        for task in tasks:
            for index,e in enumerate(task['events']):
                if 'p0' not in e:continue
                D=e['end']-e['start'];direct=self.profile(self.gateway,e['p0'],e['p1'],'T','G');cuts=list(direct.cuts);options=[]
                for r in relays:
                    if not back[r['id']] or r['service_start']>e['end'] or r['service_end']<e['start']:continue
                    p=self.profile(r['position'],e['p0'],e['p1'],'T','A');cuts+=p.cuts
                    if D>0:
                        cuts += [(v-e['start'])/D for v in [r['service_start'],r['service_end']] if e['start']<v<e['end']]
                    options.append((r,p))
                cuts=sorted(set(cuts))
                def select(t):
                    if direct.available(t):return 'direct','',direct.margin(t)
                    now=e['start']+D*t
                    for r,p in options:
                        if r['service_start']-1e-8<=now<=r['service_end']+1e-8 and p.available(t):return 'relay',r['id'],p.margin(t)
                    return 'outage','',None
                for lo,hi in zip(cuts[:-1],cuts[1:]):
                    mode,rid,margin=select((lo+hi)/2)
                    row=dict(task=task['id'],event=index,phase=e['phase'],start=e['start']+D*lo,end=e['start']+D*hi,mode=mode,relay=rid,interval='open; endpoints verified separately')
                    records.append(row)
                    if mode=='outage':fail.append(row)
                    else:
                        profile=direct if mode=='direct' else next(p for r,p in options if r['id']==rid)
                        # 同一解析分段内遮挡常量；距离范数凸，最小预算裕量在区间端点极限。
                        blocked=profile.blocked_at((lo+hi)/2)
                        dmax=max(np.linalg.norm(profile.x0+(profile.x1-profile.x0)*v-profile.z) for v in [lo,hi])
                        minmargin=min(minmargin,profile.limit-loss(self.m.comm,float(dmax),blocked))
                for t in cuts:
                    mode,rid,margin=select(t);row=dict(task=task['id'],event=index,time=e['start']+D*t,mode=mode,relay=rid)
                    endpoints.append(row)
                    if mode=='outage':fail.append(row)
                    elif margin is not None:minmargin=min(minmargin,margin)
        return dict(method='逐像元uv凸裁剪+解析距离根+全部切换端点',assumptions='分片常值闭像元DEM；经纬仿射轨迹；触地按遮挡；浮点容差单列',intervals=records,boundary_points=endpoints,failures=fail,min_access_or_direct_margin=None if not math.isfinite(minmargin) else minmargin,backhaul_available=back,profiles=len(self.cache))

def relay_task(m,position,service_start,service_end,start,drone,component,ident):
    g=m.relay;o=m.nodes['O01'];p=dict(lon=position[0],lat=position[1],work_z=position[2]);geo1=m.terrain.geometry(o,p);geo2=m.terrain.geometry(p,o)
    def calc(geo):
        t=geo['up']/g['up_speed']+geo['distance']/g['speed']+geo['down']/g['down_speed']
        e=g['power_cruise']*geo['distance']/g['speed']/3600+g['mass']*G*geo['up']/g['eta_up']/3.6e6
        return t,e
    t1,e1=calc(geo1);t2,e2=calc(geo2);ready=start+g['prep']+t1+g['link_time']
    if service_start<ready-1e-7:raise ValueError('中继未完成建链')
    # 到位后建链及等待也保守计悬停+通信功率；服务最后到返程开始无额外等候。
    energy=e1+e2+(service_end-(start+g['prep']+t1))*(g['power_hover']+g['power_comm'])/3600
    ret=service_end+t2;soc=1-energy/g['energy']
    return dict(id=ident,drone=drone,component=component,start=start,position=position,arrival=start+g['prep']+t1,service_start=service_start,ready=ready,service_end=service_end,return_time=ret,entity_ready=ret+g['turnaround'],component_ready=ret+g['turnaround']+charge(soc,g['charge_full']),energy=energy,soc=soc,flight_out=t1,flight_back=t2,geo_out=geo1,geo_back=geo2)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
