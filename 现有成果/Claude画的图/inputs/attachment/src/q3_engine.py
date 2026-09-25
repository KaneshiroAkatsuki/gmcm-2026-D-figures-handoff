import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from pathlib import Path
import sys,json,time,math,random,itertools
from collections import defaultdict,Counter
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
from dcore import Model,absolute,metrics,charge,dump,MODEL
from communication import Communications,relay_task

class Construct:
 def __init__(self):
  self.m=Model();self.cm=Communications(self.m);self.cache={};self.shape={};self.logs=[]
  spatial=json.loads((ROOT/'config/q3_config.json').read_text(encoding='utf8'))
  self.pos={i+1:r['position'] for i,r in enumerate(spatial['relays'])}
  self.travel={i:relay_task(self.m,p,1000,1001,0,'R01','EC01','temp') for i,p in self.pos.items()}
 def route(self,gid,ids):
  key=(gid,tuple(sorted(ids)))
  if key not in self.cache:self.cache[key]=self.m.route(gid,list(key[1]))
  return self.cache[key]
 def cover(self,r):
  # 相同机型/节点/箱数的轨迹与阶段时间完全相同；载荷只影响本H1的能耗。
  key=(r['type'],r['order'][0],len(r['boxes']))
  if key in self.shape:return self.shape[key]
  req=[];loc=set(range(1,5))
  for ei,e in enumerate(r['events']):
   if 'p0' not in e:continue
   d=self.cm.profile(self.cm.gateway,e['p0'],e['p1'],'T','G')
   # 无直接缺口时不构造4个接入三角面。
   if all(d.available(t) for t in d.cuts) and all(ok for lo,hi,ok in d.status_intervals()):continue
   ps=[self.cm.profile(self.pos[i],e['p0'],e['p1'],'T','A') for i in range(1,5)]
   cuts=sorted(set(d.cuts+[t for p in ps for t in p.cuts]));D=e['end']-e['start']
   for lo,hi in zip(cuts[:-1],cuts[1:]):
    mid=(lo+hi)/2
    if not d.available(mid):
     allowed={i+1 for i,p in enumerate(ps) if p.available(mid)};loc&=allowed
     req.append((e['start']+lo*D,e['start']+hi*D))
   for t in cuts:
    if not d.available(t):
     allowed={i+1 for i,p in enumerate(ps) if p.available(t)};loc&=allowed
     req.append((e['start']+t*D,e['start']+t*D))
  out=dict(locations=sorted(loc) if req else [],min_gap=min((a for a,b in req),default=None),max_gap=max((b for a,b in req),default=None),direct_only=not req)
  self.shape[key]=out;return out
 def relays(self,cfg):
  m=self.m;rel=[];component=0
  def add(d,l,start,end):
   nonlocal component
   component+=1;ready=start+self.travel[l]['ready']
   if end<=ready:return None
   r=relay_task(m,self.pos[l],ready,end,start,d,f'EC{component:02}',f'R-{component:03}');r['location']=l
   if r['soc']<.2-1e-8:return None
   rel.append(r);return r
  a=add('R01',3,0,cfg['east_end'])
  if not a:return None
  b=add('R01',1,a['entity_ready'],cfg['west_end'])
  if not b:return None
  c=add('R01',3,b['entity_ready'],cfg['final_end'])
  if not c:return None
  a=add('R02',4,0,cfg['north_end'])
  if not a:return None
  b=add('R02',2,a['entity_ready'],cfg['northwest_end'])
  if not b:return None
  c=add('R02',4,b['entity_ready'],cfg['final_end'])
  if not c:return None
  return rel
 def search(self,cfg):
  m=self.m;bs=m.boxes;relays=self.relays(cfg)
  if relays is None:return None,'relay_energy_or_order'
  timeline=defaultdict(list);remaining=set(bs);tasks=[];rng=random.Random(cfg['seed'])
  def findslot(r):
   c=self.cover(r)
   if not c['direct_only'] and not c['locations']:return None
   due=min((bs[k]['hard_due']-v for k,v in r['deliveries'].items() if bs[k]['hard_due'] is not None),default=20000)
   slots=[(0.,due,None)] if c['direct_only'] else [(max(0.,rr['service_start']-c['min_gap']+.02),min(due,rr['service_end']-c['max_gap']-.02),rr['id']) for rr in relays if rr['location'] in c['locations']]
   opts=[];dur=r['duration'];bdur=dur+charge(r['soc'],m.types[r['type']]['charge_full'])
   for lo,hi,rid in slots:
    if lo>hi:continue
    for d,g in m.drones.items():
     if g!=r['type']:continue
     for j in range(m.types[g]['batteries']):
      b=f'{g}-BAT-{j+1:02}';x=lo
      for _ in range(100):
       blocks=[end for a,end in timeline[d] if x<a+1e-8 and x+dur>a+1e-8 or x>=a-1e-8 and x<end-1e-8]
       blocks+=[end for a,end in timeline[b] if x<a+1e-8 and x+bdur>a+1e-8 or x>=a-1e-8 and x<end-1e-8]
       if not blocks:break
       x=max(blocks)
      if x<=hi+1e-8:opts.append((x,d,b,rid))
   return min(opts,key=lambda z:(z[0],z[1],z[2])) if opts else None
  def commit(r,slot):
   start,d,b,rid=slot;t=absolute(r,start,d,b,f'Q3-{len(tasks)+1:03}');t['assigned_relay_window']=rid;tasks.append(t)
   timeline[d].append((start,start+r['duration']));timeline[b].append((start,start+r['duration']+charge(r['soc'],m.types[r['type']]['charge_full'])))
   remaining.difference_update(r['boxes'])
  # 指定初批是候选构造；实体仍由可用区间选择，未来S007不堵塞此前空档。
  def pick(site,cat,limit=None):
   z=sorted(k for k in remaining if bs[k]['site']==site and cat in k)
   return z if limit is None else z[:limit]
  prescribed=cfg.get('prescribed') or [('S012','B',2),('S010','A',2),('S013','A',2),('S014','A',2),('S002','C',6),('S001','C',7),('S006',cfg['six_type'],2),('S007',cfg['seven_type'],2)]
  for site,g,n in prescribed:
   ids=pick(site,'MED',1)+pick(site,'WAT',1)
   if n==3:ids+=pick(site,'FOD',1)
   if n==1:ids=pick(site,'FOD',1)
   if n==99:ids=sorted(k for k in remaining if bs[k]['site']==site)
   if site=='S002':ids=pick(site,'MED')+pick(site,'WAT',4)+pick(site,'FOD',1)
   if site=='S001':ids=pick(site,'MED')+pick(site,'WAT',5)
   r=self.route(g,ids)
   if r is None or not m.feasible_route(r):return None,'initial_mass_energy_'+site
   slot=findslot(r)
   if slot is None:return None,'initial_no_slot_'+site
   commit(r,slot)
  def due(k):return min(bs[k]['hard_due'] or 1e9,bs[k]['expected'])-cfg['hard_advance']*(bs[k]['hard_due'] is not None)
  while remaining:
   anchor=min(remaining,key=lambda k:(due(k),-bs[k]['priority'],k));site=bs[anchor]['site'];opts=[]
   others=sorted((k for k in remaining if bs[k]['site']==site and k!=anchor),key=lambda k:(due(k),-bs[k]['mass'] if cfg['mass_first'] else -bs[k]['priority'],k))
   for gid,g in m.types.items():
    chosen=[anchor]
    for k in [None]+others:
     if k is not None:
      nr=self.route(gid,chosen+[k])
      if nr is None or not m.feasible_route(nr):continue
      chosen.append(k)
     r=self.route(gid,chosen)
     if r is None or not m.feasible_route(r):continue
     slot=findslot(r)
     if slot is None:continue
     start=slot[0];finish=start+r['deliveries'][anchor]
     urgent=sum(bs[k]['hard_due'] is not None for k in chosen)
     weighted=sum(bs[k]['priority'] for k in chosen)
     tard=sum(bs[k]['priority']*max(0,start+v-bs[k]['expected']) for k,v in r['deliveries'].items() if bs[k]['category']!='医疗物资')
     score=(finish+cfg['tard_weight']*tard/max(1,weighted))/(len(chosen)**cfg['batch_exp'])
     # 不把所有未来软货塞进首个可用窗口；记录若干评分试验。
     score*=1+cfg['c_penalty']*(gid=='C')*max(0,55-r['mass'])/55
     opts.append((score,r,slot))
   if not opts:return None,'remaining_no_slot_'+anchor
   _,r,slot=min(opts,key=lambda z:(z[0],z[2][0],z[1]['energy']));commit(r,slot)
  q=dict(model=MODEL,scope='严格H1；单点运输；四候选悬停位置；2中继6组件；启发式候选待独立复核',tasks=tasks,relays=relays,metrics=metrics(m,tasks),configuration=cfg,status='pending_full_continuous_check')
  q['joint_metrics']=dict(makespan=max([t['return_time'] for t in tasks]+[r['return_time'] for r in relays]),transport_energy=q['metrics']['energy'],relay_energy=sum(r['energy'] for r in relays),transport_sorties=len(tasks),relay_sorties=len(relays))
  return q,None

def check_resources(m,tasks,relays):
 errors=[];resources=defaultdict(list);counts=Counter(k for t in tasks for k in t['boxes'])
 if set(counts)!=set(m.boxes) or any(n!=1 for n in counts.values()):errors.append('box_coverage')
 for t in tasks:
  if t['start']<0:errors.append('negative_start '+t['id'])
  if m.drones[t['drone']]!=t['type']:errors.append('wrong_type '+t['id'])
  if not t['battery'].startswith(t['type']+'-BAT-'):errors.append('wrong_battery_type '+t['id'])
  if t['soc']<.2-1e-8:errors.append('transport_soc '+t['id'])
  resources['T/'+t['drone']].append((t['start'],t['return_time'],t['id']))
  resources['B/'+t['battery']].append((t['start'],t['return_time']+charge(t['soc'],m.types[t['type']]['charge_full']),t['id']))
  for k,v in t['deliveries'].items():
   b=m.boxes[k]
   if b['hard_due'] is not None and v>b['hard_due']+1e-7:errors.append('hard_due '+k)
 for r in relays:
  if r['drone'] not in m.relay['drones']:errors.append('relay_id '+r['id'])
  if r['start']<0 or r['service_start']<r['ready']-1e-7:errors.append('relay_time '+r['id'])
  if r['soc']<.2-1e-8:errors.append('relay_soc '+r['id'])
  z=m.terrain.height(*r['position'][:2]);agl=r['position'][2]-z
  if agl<0 or agl>m.relay['max_agl']+1e-7:errors.append('relay_agl '+r['id'])
  resources['R/'+r['drone']].append((r['start'],r['entity_ready'],r['id']))
  resources['E/'+r['component']].append((r['start'],r['component_ready'],r['id']))
 for k,items in resources.items():
  items.sort()
  for a,b in zip(items[:-1],items[1:]):
   if a[1]>b[0]+1e-7:errors.append('overlap '+k+' '+a[2]+' '+b[2])
 for g,t in m.types.items():
  if sum(k.startswith('B/'+g+'-') for k in resources)>t['batteries']:errors.append('battery_count '+g)
 if sum(k.startswith('E/') for k in resources)>6:errors.append('component_count')
 deliveries={k:v for t in tasks for k,v in t['deliveries'].items()}
 hard=min(b['hard_due']-deliveries[k] for k,b in m.boxes.items() if b['hard_due'] is not None)
 late=[dict(box=k,completion=deliveries[k],expected=b['expected'],lateness=deliveries[k]-b['expected'],priority=b['priority']) for k,b in m.boxes.items() if b['category']!='医疗物资' and deliveries[k]>b['expected']+1e-7]
 return dict(errors=errors,resources={k:items for k,items in resources.items()},box_count=len(counts),minimum_hard_slack=hard,late_nonmedical=late,scope='全输出资源/时限自检；物理依赖dcore，通信依赖communication；独立约束检查另由独立检查器执行')



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
