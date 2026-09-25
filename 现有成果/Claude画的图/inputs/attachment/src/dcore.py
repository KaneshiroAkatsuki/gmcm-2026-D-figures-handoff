import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from pathlib import Path
from functools import lru_cache
from itertools import product
import math, json, hashlib, csv
import numpy as np
import openpyxl
import tifffile

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'data' / 'original'
DATA = INPUT / '数据' / '无人机应急物资运输基础数据'
OUT = ROOT / 'output/reproduced'
G = 9.80665  # 暂用标准重力；非原题给定数值。
MODEL = 'H1_range_plus_potential_local_WGS84'

def dump(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def csvwrite(path, rows):
    rows=list(rows)
    if not rows: return
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def sheet(name, title='数据'):
    w=openpyxl.load_workbook(DATA/name,read_only=True,data_only=True)
    s=list(w[title].values);w.close();return s

def inputs():
    s=sheet('调度中心与服务区.xlsx')
    nodes={r[0]:dict(id=r[0],name=r[1],lon=r[2],lat=r[3],z=r[4],work_z=r[4]+(0 if r[0]=='O01' else 30)) for r in [s[2]]+s[6:21]}
    s=sheet('运输无人机数据.xlsx')
    keys=['id','name','mass0','capacity','volume','speed','range0','rangefull','energy','reserve_pct','prep','load_box','handover_base','handover_box','up_speed','down_speed','eta_up','eta_down']
    types={r[0]:dict(zip(keys,r)) for r in s[2:5]}
    drones={r[0]:r[1] for r in s[8:16]}
    for r in s[19:22]: types[r[0]].update(batteries=r[1],charge_full=r[2])
    s=sheet('物资需求与配送时限.xlsx','逐箱货箱清单')
    keys=['id','site','category','mass','volume','first','first_due','expected','priority']
    boxes={r[0]:dict(zip(keys,r)) for r in s[1:81]}
    for b in boxes.values():
        due=[]
        if b['category']=='医疗物资': due.append(b['expected'])
        if b['first']=='是': due.append(b['first_due'])
        b['hard_due']=min(due) if due else None
    s=sheet('中继无人机数据.xlsx')
    keys=['id','name','mass0','module_mass','mass','speed','power_cruise','energy','reserve_pct','prep','link_time','turnaround','up_speed','down_speed','eta_up','eta_down','power_hover','power_comm','max_agl']
    relay=dict(zip(keys,s[2])); relay.update(components=s[11][1],charge_full=s[11][2],drones=[s[6][0],s[7][0]])
    c=sheet('通信链路参数.xlsx');v=lambda row:c[row-1][4]
    comm=dict(f=v(3),system=v(4),obstruction=v(5),sensitivity=v(6),fade=v(7),T=(v(8),v(9)),A=(v(10),v(11)),R=(v(12),v(13)),G=(v(14),v(15)),gateway_height=v(16))
    return nodes,types,drones,boxes,relay,comm

class Terrain:
    def __init__(self,nodes):
        p=next(INPUT.rglob('*.tif'))
        with tifffile.TiffFile(p) as t:
            self.a=t.asarray(); m=t.geotiff_metadata
        self.dx,self.dy=m['ModelPixelScale'][:2]
        self.x0,self.y0=m['ModelTiepoint'][3:5]
        assert int(m['GTRasterTypeGeoKey'])==2, '必须重核栅格坐标定义'
        self.left=self.x0-self.dx/2;self.top=self.y0+self.dy/2
        self.origin=nodes['O01'];phi=math.radians(self.origin['lat'])
        a=6378137.;e2=6.6943799901413165e-3
        self.kx=math.pi/180*a/math.sqrt(1-e2*math.sin(phi)**2)*math.cos(phi)
        self.ky=math.pi/180*a*(1-e2)/(1-e2*math.sin(phi)**2)**1.5
    def xy(self,lon,lat): return np.array([(lon-self.origin['lon'])*self.kx,(lat-self.origin['lat'])*self.ky])
    def lonlat(self,x,y):return (self.origin['lon']+x/self.kx,self.origin['lat']+y/self.ky)
    def grid(self,lon,lat):return ((lon-self.left)/self.dx,(self.top-lat)/self.dy)
    def height(self,lon,lat):
        x,y=self.grid(lon,lat);r,c=math.floor(y),math.floor(x)
        if not (0<=r<self.a.shape[0] and 0<=c<self.a.shape[1]):raise ValueError('DEM外')
        z=float(self.a[r,c]);assert math.isfinite(z) and z!=-32767;return z
    def cells(self,a,b):
        """全网格交点分段；角点和沿边的相邻像元均纳入。返回像元参数闭区间。"""
        x,y=self.grid(a[0],a[1]);u,v=self.grid(b[0],b[1]);dx=u-x;dy=v-y
        ts=[0.,1.]
        for p,d,q in [(x,dx,u),(y,dy,v)]:
            if abs(d)>1e-14:
                ts.extend((k-p)/d for k in range(math.ceil(min(p,q)),math.floor(max(p,q))+1) if 0<(k-p)/d<1)
        ts=np.unique(ts);found={}
        def idx(p):
            k=round(p)
            return [k-1,k] if abs(p-k)<1e-8 else [math.floor(p)]
        def add(t,lo,hi):
            for c,r in product(idx(x+dx*t),idx(y+dy*t)):
                if not (0<=r<self.a.shape[0] and 0<=c<self.a.shape[1]):raise ValueError('航段离开DEM')
                key=(r,c)
                old=found.get(key,(lo,hi));found[key]=(min(lo,old[0]),max(hi,old[1]))
        for t in ts:add(t,float(t),float(t))
        for lo,hi in zip(ts[:-1],ts[1:]):add((lo+hi)/2,float(lo),float(hi))
        result=[]
        for (r,c),(lo,hi) in sorted(found.items()):
            z=float(self.a[r,c]);assert math.isfinite(z) and z!=-32767
            result.append((r,c,lo,hi,z))
        return result
    def geometry(self,a,b):
        cells=self.cells((a['lon'],a['lat']),(b['lon'],b['lat']))
        zmax=max(z for _,_,_,_,z in cells);h=zmax+50
        up=h-a['work_z'];down=h-b['work_z']
        if min(up,down)<-1e-7:raise ValueError('题定巡航海拔低于节点作业高度，需要核原件')
        return dict(distance=float(np.linalg.norm(self.xy(a['lon'],a['lat'])-self.xy(b['lon'],b['lat']))),terrain_max=zmax,cruise_z=h,up=up,down=down,cells=len(cells))
    def los(self,a,b):
        """分片常值DEM解释：逐像元比较视线高度的最小值，触地视为遮挡。"""
        cells=self.cells(a,b)
        return all(min(a[2]+(b[2]-a[2])*lo,a[2]+(b[2]-a[2])*hi)>z+1e-8 for _,_,lo,hi,z in cells)

def charge(s,full):
    if not -1e-8<=s<=1+1e-8:raise ValueError('SOC越界')
    s=min(1,max(0,s))
    return full*(.65*(.9-s)/.9+.35) if s<.9 else full*.35*(1-s)/.1

def leg(g,geo,q):
    assert -1e-8<=q<=g['capacity']+1e-8
    L=g['range0']-(g['range0']-g['rangefull'])*(max(0,q)/g['capacity'])**1.5
    eh=g['energy']*geo['distance']/L
    eu=(g['mass0']+q)*G*geo['up']/g['eta_up']/3.6e6
    return dict(time=geo['up']/g['up_speed']+geo['distance']/g['speed']+geo['down']/g['down_speed'],energy=eh+eu,horizontal_energy=eh,up_energy=eu,range=L)

def budget(comm,a,b):
    pa,ga=comm[a];pb,gb=comm[b]
    return min(pa,pb)+ga+gb-comm['system']-(comm['sensitivity']+comm['fade'])

def loss(comm,distance_m,blocked):
    if distance_m<=0:return float('-inf')
    return 32.45+20*math.log10(comm['f'])+20*math.log10(distance_m/1000)+comm['obstruction']*blocked

def guaranteed_radius(comm,a,b):
    return 1000*10**((budget(comm,a,b)-comm['obstruction']-32.45-20*math.log10(comm['f']))/20)

class Model:
    def __init__(self):
        self.nodes,self.types,self.drones,self.boxes,self.relay,self.comm=inputs();self.terrain=Terrain(self.nodes)
        self.geo={(a,b):self.terrain.geometry(na,nb) for a,na in self.nodes.items() for b,nb in self.nodes.items() if a!=b}
    def route(self,gid,box_ids,order=None):
        g=self.types[gid];bs=[self.boxes[i] for i in box_ids]
        if order is None:order=list(dict.fromkeys(b['site'] for b in bs))
        assert set(order)=={b['site'] for b in bs} and len(order)==len(set(order))
        mass=sum(b['mass'] for b in bs);vol=sum(b['volume'] for b in bs)
        if mass>g['capacity']+1e-9 or vol>g['volume']+1e-9:return None
        now=g['prep']+g['load_box']*len(bs);q=mass;prev='O01';energy=0.;deliveries={};legs=[];events=[]
        events.append(dict(phase='准备装载',start=0.,end=now,node='O01'))
        for dest in order+['O01']:
            geo=self.geo[prev,dest];calc=leg(g,geo,q)
            a=self.nodes[prev];b=self.nodes[dest];tup=geo['up']/g['up_speed'];tc=geo['distance']/g['speed'];td=geo['down']/g['down_speed']
            positions=[(a['lon'],a['lat'],a['work_z']),(a['lon'],a['lat'],geo['cruise_z']),(b['lon'],b['lat'],geo['cruise_z']),(b['lon'],b['lat'],b['work_z'])]
            for k,(dur,phase) in enumerate(zip([tup,tc,td],['爬升','巡航','下降'])):
                events.append(dict(phase=phase,start=now,end=now+dur,p0=positions[k],p1=positions[k+1],from_node=prev,to_node=dest));now+=dur
            energy+=calc['energy'];legs.append(dict(from_node=prev,to_node=dest,payload=q,**geo,**calc))
            if dest!='O01':
                cargo=[b for b in bs if b['site']==dest];dur=g['handover_base']+g['handover_box']*len(cargo)
                events.append(dict(phase='交接',start=now,end=now+dur,p0=positions[-1],p1=positions[-1],node=dest))
                now+=dur
                # 保守事件口径：该站所有箱均以整批交接完成记交付，不抢用到达或逐箱中间时刻。
                for b in cargo:deliveries[b['id']]=now
                q-=sum(b['mass'] for b in cargo)
            prev=dest
        return dict(type=gid,boxes=list(box_ids),order=order,mass=mass,volume=vol,duration=now,flight_time=sum(l['time'] for l in legs),energy=energy,soc=1-energy/g['energy'],deliveries=deliveries,legs=legs,events=events)
    def feasible_route(self,r,rho=.2):return r is not None and r['soc']>=rho-1e-10
    def max_payload(self,gid,site,rho=.2):
        g=self.types[gid]
        def e(q):return leg(g,self.geo['O01',site],q)['energy']+leg(g,self.geo[site,'O01'],0)['energy']
        limit=(1-rho)*g['energy']
        if e(0)>limit:return dict(status='unreachable',payload=None)
        if e(g['capacity'])<=limit:return dict(status='capacity_limited',payload=g['capacity'])
        lo=0.;hi=g['capacity']
        for _ in range(60):
            mid=(lo+hi)/2
            if e(mid)<=limit:lo=mid
            else:hi=mid
        return dict(status='energy_limited',payload=lo)

def absolute(r,start,drone,battery,ident):
    r=json.loads(json.dumps(r));r.update(id=ident,start=start,drone=drone,battery=battery,return_time=start+r['duration'])
    r['deliveries']={k:v+start for k,v in r['deliveries'].items()}
    for e in r['events']:e['start']+=start;e['end']+=start
    return r

def metrics(m,tasks):
    deliveries={k:v for t in tasks for k,v in t['deliveries'].items()}
    soft=[b for b in m.boxes.values() if b['category']!='医疗物资']
    hard_violations=[b['id'] for b in m.boxes.values() if b['hard_due'] is not None and deliveries.get(b['id'],math.inf)>b['hard_due']+1e-7]
    return dict(sorties=len(tasks),energy=sum(t['energy'] for t in tasks),cumulative_time=sum(t['duration'] for t in tasks),makespan=max(t.get('return_time',t['duration']) for t in tasks),delivered=len(deliveries),hard_violations=hard_violations,weighted_soft_tardiness=sum(b['priority']*max(0,deliveries.get(b['id'],1e9)-b['expected']) for b in soft),soft_late_count=sum(deliveries.get(b['id'],1e9)>b['expected']+1e-7 for b in soft))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
