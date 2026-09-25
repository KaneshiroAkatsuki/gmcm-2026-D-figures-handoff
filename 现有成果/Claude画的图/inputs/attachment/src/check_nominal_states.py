import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D,localcontext
import argparse,hashlib,json,math,time
from collections import defaultdict
import numpy as np
from independent_check import read_originals
from independent_rational_shadow import cell_shadow
from check_q3_plan_v0031 import IndependentLinks,PROJECT


def asdec(x):
    return D(x.numerator)/D(x.denominator) if isinstance(x,F) else D(str(x))


def merge(intervals):
    union=[]
    for lo,hi in sorted(intervals):
        if union and lo<=union[-1][1]:union[-1][1]=max(hi,union[-1][1])
        else:union.append([lo,hi])
    return union


def shadows_by_vertex_enumeration(terrain,basis):
    B,A,Z=([F(s) for s in basis[k]] for k in ['B','A','Z'])
    v=np.array([[float(x) for x in t] for t in [B,A,Z]])
    rows=np.arange(max(0,math.ceil(v[:,1].min())-1),min(terrain.shape[0],math.floor(v[:,1].max())+1))
    cols=np.arange(max(0,math.ceil(v[:,0].min())-1),min(terrain.shape[1],math.floor(v[:,0].max())+1))
    xx,yy=np.meshgrid(cols,rows);mask=np.ones(xx.shape,dtype=bool)
    # Only discard cells separated from the full swept triangle. This outward
    # filter is deliberately looser than the exact subsequent rational proof.
    for p,q in zip(v,np.roll(v,-1,axis=0)):
        nx,ny=q[1]-p[1],p[0]-q[0]
        dot=v[:,0]*nx+v[:,1]*ny
        low=nx*xx+ny*yy+min(nx,0)+min(ny,0)
        high=nx*xx+ny*yy+max(nx,0)+max(ny,0)
        pad=1e-6*(1+abs(nx)+abs(ny))
        mask &= (high>=dot.min()-pad)&(low<=dot.max()+pad)
    mask &= terrain[yy,xx]>=v[:,2].min()-1e-6
    intervals=[];count=0
    for row,col in zip(yy[mask],xx[mask]):
        h=float(terrain[row,col])
        if not math.isfinite(h) or h==-32767:raise ValueError('NoData in candidate shadow cell')
        pair=cell_shadow(B,A,Z,int(row),int(col),F(str(h)));count+=1
        if pair is not None:intervals.append(pair)
    return merge(intervals),count


def run(plan_path,state_path):
    started=time.perf_counter();plan=json.loads(plan_path.read_text(encoding='utf-8'));data=json.loads(state_path.read_text(encoding='utf-8'))
    original=PROJECT/'data/original';nodes,*_=read_originals(original)
    nominal=IndependentLinks(original,nodes);robust=IndependentLinks(original,nodes,.01,1)
    tasks={x['id']:x for x in plan['tasks']};relays={x['id']:x for x in plan['relays']}
    proofrows=defaultdict(list)
    for row in plan['communication']['intervals']:proofrows[row['task'],row['event']].append(row)
    errors=[];profiles={};cache={};basis_deviations=[];checked_cells=0;maximum_root_error=D(0)
    expected_events={(tid,i) for tid,task in tasks.items() for i,e in enumerate(task['events']) if 'p0' in e}
    supplied_events=[(p['task'],p['event']) for p in data['analytic_profiles']]
    if set(supplied_events)!=expected_events or len(supplied_events)!=len(set(supplied_events)):
        errors.append(dict(kind='profile_event_coverage'))
    if len({p['id'] for p in data['analytic_profiles']})!=len(data['analytic_profiles']):errors.append(dict(kind='duplicate_profile_id'))
    if data.get('delta_db')!=0 or data.get('clearance_m')!=0:errors.append(dict(kind='nominal_parameter_metadata'))
    if data.get('failures'):errors.append(dict(kind='producer_recorded_failures',failures=data['failures']))
    radius_clear=D(1000)*D(10)**((D(str(nominal.p['limits']['direct']))-D('32.45')-20*D(str(nominal.p['frequency'])).log10())/20)
    radius_block=radius_clear/(D(10)**(D(str(nominal.p['obstruction']))/20))
    numerical_encoding_tolerance=D('1e-70')
    for ix,source in enumerate(data['analytic_profiles']):
        tid=source['task'];ei=source['event'];e=tasks[tid]['events'][ei]
        xyz=[[D(s) for s in row] for row in source['xyz_basis']]
        points=[nominal.gateway,e['p0'],e['p1']]
        xyz_error=max(abs(float(a)-float(b)) for pos,row in zip(points,xyz) for a,b in zip(nominal.xyz(pos),row))
        B,A,Z=xyz;w=[a-b for a,b in zip(A,B)];v=[z-a for z,a in zip(Z,A)]
        aa=sum(x*x for x in v);bb=2*sum(x*y for x,y in zip(w,v));cc=sum(x*x for x in w)
        for found,expected in zip(source['polynomial'],[aa,bb,cc]):
            if abs(D(found)-expected)>numerical_encoding_tolerance*max(D(1),abs(expected)):errors.append(dict(kind='polynomial',task=tid,event=ei))
        for found,expected in zip(source['radii'],[radius_block,radius_clear]):
            if abs(D(found)-expected)>numerical_encoding_tolerance*max(D(1),abs(expected)):errors.append(dict(kind='radius',task=tid,event=ei))
        guaranteed=max(cc,aa+bb+cc)<=radius_block*radius_block
        pixel_error=0.0
        if not guaranteed:
            basis=source['pixel_basis']
            if not basis:
                errors.append(dict(kind='missing_pixel_basis',task=tid,event=ei));continue
            for pos,key in zip(points,['B','A','Z']):
                pixel_error=max(pixel_error,max(abs(a-float(F(b))) for a,b in zip(nominal.los.pixel(pos),basis[key])))
            cachekey=json.dumps(basis,sort_keys=True)
            if cachekey not in cache:
                cache[cachekey]=shadows_by_vertex_enumeration(nominal.los.terrain,basis)
                checked_cells+=cache[cachekey][1]
            shadows,_=cache[cachekey]
            supplied=[[F(a),F(b)] for a,b in source['shadow_rational']]
            if supplied!=shadows:errors.append(dict(kind='shadow_union_mismatch',task=tid,event=ei,found=source['shadow_rational'],expected=[[str(a),str(b)] for a,b in shadows]))
        else:shadows=[]
        # Coordinate reconstruction tolerance only measures binary64 arithmetic
        # equivalence, not link feasibility; acceptance remains strict 0/.01.
        basis_deviations.append(dict(task=tid,event=ei,xyz_max_abs_m=xyz_error,pixel_max_abs_pixel=pixel_error))
        if xyz_error>1e-7 or pixel_error>1e-7:errors.append(dict(kind='basis_not_reproduced',task=tid,event=ei,xyz_error=xyz_error,pixel_error=pixel_error))
        expected=[(D(0),'event'),(D(1),'event')]
        for r,tag in [(radius_block,'blocked_radius'),(radius_clear,'clear_radius')]:
            disc=bb*bb-4*aa*(cc-r*r)
            if aa>0 and disc>=0:
                for t in [(-bb-disc.sqrt())/(2*aa),(-bb+disc.sqrt())/(2*aa)]:
                    if 0<=t<=1:expected.append((t,tag))
        for lo,hi in shadows:expected.extend([(asdec(lo),'shadow'),(asdec(hi),'shadow')])
        encoded=[(D(r['t']),tag) for r in source['critical_parameters'] for tag in r['kinds']]
        for t,tag in expected:
            matches=[abs(t-x) for x,other in encoded if other==tag]
            error=min(matches,default=D('Infinity'));maximum_root_error=max(maximum_root_error,error)
            if error>numerical_encoding_tolerance:errors.append(dict(kind='missing_analytic_switch',task=tid,event=ei,tag=tag,t=str(t)))
        for t,tag in encoded:
            if min((abs(t-x) for x,other in expected if other==tag),default=D('Infinity'))>numerical_encoding_tolerance:
                errors.append(dict(kind='spurious_analytic_switch',task=tid,event=ei,tag=tag,t=str(t)))
        profiles[source['id']]=dict(source=source,aa=aa,bb=bb,cc=cc,guaranteed=guaranteed,shadows=shadows,critical=expected)
        if (ix+1)%28==0:print(f'profiles {ix+1}/{len(data["analytic_profiles"])} checked; distinct shadow cells={checked_cells}',flush=True)
    # Once every possible zero/crossing is present, one interior sign determines
    # the entire open interval. This is an analytic decomposition, not sampling.
    def availability(profile,t,boundary):
        if profile['guaranteed']:return True
        near=[(x,tag) for x,tag in profile['critical'] if abs(x-t)<=numerical_encoding_tolerance]
        if boundary and any(tag=='shadow' for x,tag in near):
            # Terrain contact belongs to the blocked state.
            blocked=True
        else:blocked=any(asdec(lo)<=t<=asdec(hi) for lo,hi in profile['shadows'])
        radius=radius_block if blocked else radius_clear
        tag='blocked_radius' if blocked else 'clear_radius'
        if boundary and any(k==tag for x,k in near):return True
        return profile['aa']*t*t+profile['bb']*t+profile['cc']<=radius*radius
    grouped=defaultdict(list);pointed=defaultdict(list);relay_checks=0
    for row in data['intervals']:grouped[row['task'],row['event']].append(row)
    for row in data['boundary_points']:pointed[row['task'],row['event']].append(row)
    if set(grouped)!=expected_events or set(pointed)!=expected_events:errors.append(dict(kind='row_event_coverage'))
    physical_boundaries=defaultdict(list)
    for row in data['boundary_points']:
        physical_boundaries[row['task'],D(row['time_exact_decimal'])].append(row)
    for (tid,t),rows_at_time in physical_boundaries.items():
        providers={(r['mode'],r['relay']) for r in rows_at_time}
        if len(providers)>1:errors.append(dict(kind='nonunique_physical_boundary_provider',task=tid,time=str(t),providers=sorted(providers)))
    for profile_id,pr in profiles.items():
        source=pr['source'];key=(source['task'],source['event']);e=tasks[key[0]]['events'][key[1]]
        rows=sorted(grouped[key],key=lambda x:D(x['parameter_start']));points=pointed[key]
        endpoints=[]
        if not rows or D(rows[0]['parameter_start'])!=0 or D(rows[-1]['parameter_end'])!=1:errors.append(dict(kind='event_coverage',task=key[0],event=key[1]))
        for a,b in zip(rows,rows[1:]):
            if a['parameter_end']!=b['parameter_start']:errors.append(dict(kind='partition_gap',task=key[0],event=key[1]))
        for row in rows:
            lo,hi=D(row['parameter_start']),D(row['parameter_end']);endpoints.extend([lo,hi])
            if not lo<hi or not row['start']<row['end']:errors.append(dict(kind='zero_or_reversed_interval',task=key[0],event=key[1]))
            for t,tag in pr['critical']:
                if lo+numerical_encoding_tolerance<t<hi-numerical_encoding_tolerance:errors.append(dict(kind='unpartitioned_switch',task=key[0],event=key[1],t=str(t),tag=tag))
        for row in rows+points:
            ispoint='parameter' in row;lo=D(row['parameter']) if ispoint else D(row['parameter_start']);hi=lo if ispoint else D(row['parameter_end'])
            available=availability(pr,(lo+hi)/2,ispoint);expected='direct' if available else 'relay'
            if row['mode']!=expected:errors.append(dict(kind='state_label',task=key[0],event=key[1],parameter=str(lo),found=row['mode'],expected=expected,point=ispoint))
            if row['nominal_profile']!=profile_id:errors.append(dict(kind='wrong_profile',task=key[0],event=key[1]))
            start=D(str(e['start']));duration=D(str(e['end']))-start
            for t,text,number in [(lo,row['time_exact_decimal'] if ispoint else row['start_exact_decimal'],row['time'] if ispoint else row['start']),
                                  (hi,row['time_exact_decimal'] if ispoint else row['end_exact_decimal'],row['time'] if ispoint else row['end'])]:
                precise=start+duration*t
                if abs(D(text)-precise)>numerical_encoding_tolerance*max(D(1),abs(precise)) or float(D(text))!=number:
                    errors.append(dict(kind='time_encoding',task=key[0],event=key[1]))
            if expected=='relay':
                rid=row['relay'];low=row['time'] if ispoint else row['start'];high=row['time'] if ispoint else row['end']
                candidates=list(proofrows[key])
                if ispoint:
                    # A phase junction is one physical instant. A unique
                    # provider may be inherited from either adjacent event,
                    # but only when both exact stored endpoint positions match.
                    anchor_position=e['p0'] if low==e['start'] else e['p1'] if low==e['end'] else None
                    if anchor_position is not None:
                        for other_i,other_e in enumerate(tasks[key[0]]['events']):
                            other_position=other_e.get('p0') if low==other_e['start'] else other_e.get('p1') if low==other_e['end'] else None
                            if other_position==anchor_position:candidates.extend(proofrows[key[0],other_i])
                inherited=any(x.get('relay')==rid and x['start']<=low<=high<=x['end'] for x in candidates)
                if not inherited:errors.append(dict(kind='new_binding',task=key[0],event=key[1],relay=rid))
                if rid not in relays:errors.append(dict(kind='unknown_relay',relay=rid));continue
                r=relays[rid]
                if not max(r['ready'],r['service_start'])<=low<=high<=r['service_end']:errors.append(dict(kind='relay_service_window',relay=rid))
                def position(seconds):
                    u=(seconds-e['start'])/(e['end']-e['start']) if e['end']!=e['start'] else 0
                    return (np.array(e['p0'])+(np.array(e['p1'])-e['p0'])*u).tolist()
                access=robust.certify(r['position'],position(low),position(high),'access',point=ispoint)
                backhaul=robust.certify(robust.gateway,r['position'],r['position'],'backhaul',point=True)
                relay_checks+=1
                if access['status']!='certified' or backhaul['status']!='certified':errors.append(dict(kind='relay_robust_certificate',task=key[0],event=key[1],relay=rid,access=access,backhaul=backhaul))
        for t in set(endpoints):
            if not any(D(x['parameter'])==t for x in points):errors.append(dict(kind='missing_exact_boundary',task=key[0],event=key[1],t=str(t)))
    return dict(passed=not errors,errors=errors,plan_source=str(plan_path),plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                state_source=str(state_path),state_sha256=hashlib.sha256(state_path.read_bytes()).hexdigest(),
                profile_count=len(profiles),interval_count=len(data['intervals']),boundary_count=len(data['boundary_points']),
                distinct_shadow_profiles=len(cache),independently_enumerated_shadow_cells=checked_cells,
                relay_closed_certificates_rechecked=relay_checks,decimal_verification_digits=100,
                max_analytic_switch_encoding_difference=str(maximum_root_error),
                max_xyz_basis_difference_m=max(x['xyz_max_abs_m'] for x in basis_deviations),
                max_pixel_basis_difference_pixel=max(x['pixel_max_abs_pixel'] for x in basis_deviations),
                basis_comparisons=basis_deviations,elapsed_s=time.perf_counter()-started,
                limitations=['Archived binary64 endpoint constants define the numerical geometric model; independent reconstruction differs only by measured arithmetic rounding.',
                             '80-digit decimal numbers encode independently checked symbolic analytic switches; Excel binary64 is a display approximation.',
                             'Open intervals exclude switch instants; all boundary instants are separately classified, budget equality available and terrain contact blocked.',
                             'The 1e-70 check compares numerical encodings at 80 versus 100 decimal digits, and never relaxes a communication loss or clearance gate.'])



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
