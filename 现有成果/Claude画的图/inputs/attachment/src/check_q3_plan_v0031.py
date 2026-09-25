from __future__ import annotations
import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from fractions import Fraction
import numpy as np
from independent_check import audit,read_originals,sheet,Terrain,local_distance,charge_seconds,G
from check_formal_outputs import Findings,check_solution

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parent
LOS_SOURCE=OUT/"independent_triangle_los.py"
SHADOW_SOURCE=OUT/"independent_rational_shadow.py"


def load_los(path):
    spec=importlib.util.spec_from_file_location("independent_triangle_los",LOS_SOURCE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.TifLOS(path)


def relay_parameters(original):
    c=sheet(next(original.rglob("中继无人机数据.xlsx")))
    names={"E":"mass","F":"speed","G":"cruise_power","H":"energy","I":"reserve_pct","J":"prep",
           "K":"link","L":"turnaround","M":"climb_speed","N":"descent_speed","O":"eta","Q":"hover_power","R":"communication_power","S":"height_limit"}
    values={key:float(c[col+"3"]) for col,key in names.items()}
    values.update(component_count=int(c["B12"]),full_charge=float(c["C12"]),entities={c["A7"],c["A8"]})
    return values


def comm_parameters(original):
    c=sheet(next(original.rglob("通信链路参数.xlsx")))
    vals={int(key[1:]):float(value) for key,value in c.items() if key.startswith("E") and key[1:].isdigit() and value and int(key[1:]) in range(3,17)}
    devices={"T":(vals[8],vals[9]),"A":(vals[10],vals[11]),"R":(vals[12],vals[13]),"G":(vals[14],vals[15])}
    limits={}
    for name,left,right in [("direct","T","G"),("access","T","A"),("backhaul","R","G")]:
        pl,gl=devices[left];pr,gr=devices[right]
        # Independently compute both directions before taking the minimum.
        limits[name]=min(pl+gl+gr-vals[4]-vals[6]-vals[7],pr+gr+gl-vals[4]-vals[6]-vals[7])
    return dict(frequency=vals[3],obstruction=vals[5],gateway_height=vals[16],limits=limits)


def resource_check(data,original,nodes):
    f=Findings();g=relay_parameters(original);tif=next(original.rglob("*.tif"));terrain=Terrain(tif)
    records=[];aircraft=defaultdict(list);components=defaultdict(list);ids=[]
    for r in data.get("relays",[]):
        tid=r.get("id","unknown");ids.append(tid);pos=r["position"]
        f.require(len(pos)==3 and all(math.isfinite(v) for v in pos),tid,"Invalid relay position")
        point=dict(lon=pos[0],lat=pos[1],operation_m=pos[2]);x,y=terrain.pixel(point)
        in_dem=0<=x<terrain.dem.shape[1] and 0<=y<terrain.dem.shape[0]
        f.require(in_dem,tid,"Relay point outside original DEM")
        if not in_dem:continue
        ground=float(terrain.dem[math.floor(y),math.floor(x)])
        f.require(math.isfinite(ground) and ground!=-32767,tid,"Relay point NoData")
        agl=pos[2]-ground
        f.require(-1e-8<=agl<=g["height_limit"]+1e-8,tid,"Relay AGL not in [0,300] m")
        outbound=terrain.segment(nodes["O01"],point);h=outbound["max_ground_m"]+50
        distance=local_distance(nodes["O01"],point,nodes["O01"])
        geo_out=dict(distance=distance,terrain_max=outbound["max_ground_m"],cruise_z=h,up=h-nodes["O01"]["operation_m"],down=h-pos[2],cells=outbound["cell_count"])
        geo_back={**geo_out,"up":geo_out["down"],"down":geo_out["up"]}
        valid_flight=min(geo_out["up"],geo_out["down"])>=-1e-8
        f.require(valid_flight,tid,"Strict maximum-terrain+50 cruise level lies below an operation endpoint")
        if not valid_flight:continue
        for field,geo in [("geo_out",geo_out),("geo_back",geo_back)]:
            for key,value in geo.items():f.close(r.get(field,{}).get(key),value,tid+"."+field+"."+key)
        def flight(geo):
            seconds=geo["up"]/g["climb_speed"]+distance/g["speed"]+geo["down"]/g["descent_speed"]
            energy=g["cruise_power"]*(distance/g["speed"])/3600+g["mass"]*G*geo["up"]/(g["eta"]*3.6e6)
            return seconds,energy
        t_out,e_out=flight(geo_out);t_back,e_back=flight(geo_back)
        start=r["start"];arrival=start+g["prep"]+t_out;ready=arrival+g["link"]
        f.require(start>=0,tid,"Negative relay preparation start")
        f.require(r["service_start"]>=ready-1e-7,tid,"Relay service starts before arrival and link establishment")
        f.require(r["service_end"]>=r["service_start"]-1e-8,tid,"Relay service end precedes start")
        energy=e_out+e_back+(r["service_end"]-arrival)*(g["hover_power"]+g["communication_power"])/3600
        ret=r["service_end"]+t_back;soc=1-energy/g["energy"];entity_ready=ret+g["turnaround"]
        f.require(g["reserve_pct"]/100-1e-9<=soc<=1+1e-9,tid,"Relay return SOC violates reserve or conservation")
        component_ready=entity_ready+charge_seconds(min(1,max(0,soc)),g["full_charge"])
        expected=dict(arrival=arrival,ready=ready,return_time=ret,entity_ready=entity_ready,component_ready=component_ready,energy=energy,soc=soc,flight_out=t_out,flight_back=t_back)
        for key,value in expected.items():
            if key in ["flight_out","flight_back"] and key not in r:continue
            f.close(r.get(key),value,tid+"."+key)
        f.require(r.get("drone") in g["entities"],tid,"Unknown relay entity")
        f.require(isinstance(r.get("component"),str) and bool(r["component"]),tid,"Missing energy component ID")
        aircraft[r["drone"]].append((start,entity_ready,tid));components[r["component"]].append((start,component_ready,tid))
        records.append(dict(id=tid,agl_m=agl,ground_m=ground,**expected))
    f.require(len(ids)==len(set(ids)),"relays","Duplicate relay sortie IDs")
    f.require(len(components)<=g["component_count"],"relays","More than 6 distinct energy components")
    for category,items in [("relay_aircraft",aircraft),("relay_component",components)]:
        for ident,intervals in items.items():
            intervals.sort()
            for first,second in zip(intervals,intervals[1:]):f.require(first[1]<=second[0]+1e-6,category+"."+ident,f"Conflict: {first} / {second}")
    return dict(passed=not f.errors,errors=f.errors,comparison_count=f.comparisons,relays=records,
                energy_kwh=sum(r["energy"] for r in records),last_return_s=max((r["return_time"] for r in records),default=0),
                aircraft_intervals=dict(aircraft),component_intervals=dict(components),
                assumptions=["Strict cruise=max crossed DEM+50m", "H1 potential-energy climb interpretation", "Link establishment and waiting use hover+communication 1.1kW", "Entity held through return+300s turnaround", "Component charging conservatively starts after 300s turnaround", "AGL uses containing pixel; closed neighbors used for route terrain"])


class IndependentLinks:
    def __init__(self,original,nodes,delta_g_db=0.0,clearance_m=0.0,regression_legacy_roundoff=False):
        if delta_g_db < 0 or clearance_m < 0: raise ValueError("Negative acceptance gate")
        if regression_legacy_roundoff and (delta_g_db != 0 or clearance_m != 0):
            raise ValueError("Legacy roundoff is permitted only for 0,0 regression")
        self.delta_g_db=float(delta_g_db);self.clearance_m=float(clearance_m)
        self.budget_roundoff_db=1e-8 if regression_legacy_roundoff else 0.0
        self.p=comm_parameters(original);self.origin=nodes["O01"];o=self.origin
        self.gateway=[o["lon"],o["lat"],o["ground_m"]+self.p["gateway_height"]]
        self.los=load_los(next(original.rglob("*.tif")));self.cache={};self.unavailable_cache={}
        # Raise every valid DEM cell, preserving NoData sentinel. This is the
        # explicit c gate. The LOS engine still requires strictly positive
        # residual clearance; equality is conservatively not certified.
        self.los.terrain=self.los.terrain.astype(float)
        valid=np.isfinite(self.los.terrain)&(self.los.terrain!=-32767)
        self.los.terrain[valid]+=self.clearance_m
        spec=importlib.util.spec_from_file_location("independent_rational_shadow",SHADOW_SOURCE)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);self.cell_shadow=module.cell_shadow
    def xyz(self,position):
        lon,lat,z=position;phi=math.radians(self.origin["lat"]);a=6378137.;f=1/298.257223563;e2=f*(2-f)
        w=math.sqrt(1-e2*math.sin(phi)**2);n=a/w;m=a*(1-e2)/w**3
        return np.array([math.radians(lon-self.origin["lon"])*n*math.cos(phi),math.radians(lat-self.origin["lat"])*m,z])
    def loss(self,d,blocked):
        return -math.inf if d<=0 else 32.45+20*math.log10(self.p["frequency"])+20*math.log10(d/1000)+self.p["obstruction"]*blocked
    def certify(self,anchor,p0,p1,kind,point=False):
        key=(tuple(anchor),tuple(p0),tuple(p1),kind,point)
        if key in self.cache:return self.cache[key]
        b=self.xyz(anchor);d=max(np.linalg.norm(self.xyz(p)-b) for p in [p0,p1]);budget=self.p["limits"][kind]-self.delta_g_db
        worst=budget-self.loss(d,True);clear=budget-self.loss(d,False)
        if worst>=-self.budget_roundoff_db:result=dict(status="certified",method="convex_distance_endpoints_with_full_10dB_obstruction",margin_lower_db=worst)
        elif clear<-self.budget_roundoff_db:result=dict(status="failed",method="clear_link_range_exceeded_at_endpoint_limit",margin_clear_db=clear)
        else:
            certificate=self.los(anchor,p0,p1)
            if certificate["certified"]:result=dict(status="certified",method="all_time_3D_triangle_LOS_and_endpoint_distance",margin_lower_db=clear,los=certificate)
            elif point and "min_clearance_m" in certificate and certificate["min_clearance_m"]<=0:
                result=dict(status="failed",method="independent_static_LOS_blocked_and_budget_insufficient",margin_blocked_db=worst,los=certificate)
            else:result=dict(status="unresolved",method="LOS_certificate_not_obtained_including_open_interval_boundaries",los=certificate,margin_clear_db=clear,margin_blocked_db=worst)
        if "margin_lower_db" in result:
            result["nominal_budget_margin_lower_db"]=result["margin_lower_db"]+self.delta_g_db
        result.update(delta_g_db=self.delta_g_db,clearance_m=self.clearance_m,budget_roundoff_db=self.budget_roundoff_db)
        self.cache[key]=result;return result
    def certify_unavailable(self,anchor,p0,p1,kind,point=False):
        key=(tuple(anchor),tuple(p0),tuple(p1),kind,point)
        if key in self.unavailable_cache:return self.unavailable_cache[key]
        b=self.xyz(anchor);x0=self.xyz(p0)-b;v=self.xyz(p1)-self.xyz(p0)
        den=float(v@v);s=min(1,max(0,-float(x0@v)/den)) if den else 0
        dmin=float(np.linalg.norm(x0+s*v));limit=self.p["limits"][kind]-self.delta_g_db
        best_clear_margin=limit-self.loss(dmin,False);best_blocked_margin=limit-self.loss(dmin,True)
        if best_clear_margin<-self.budget_roundoff_db:
            result=dict(certified=True,method="minimum_distance_clear_budget_exceeded",best_margin_db=best_clear_margin)
        elif best_blocked_margin>=-self.budget_roundoff_db:
            result=dict(certified=False,method="blocked_budget_not_strictly_insufficient_on_whole_interval",best_blocked_margin_db=best_blocked_margin)
        else:
            B=self.los.pixel(anchor);A0=self.los.pixel(p0);A1=self.los.pixel(p1)
            shadows=[];evidence=[];seen=set();reason="uncovered_time"
            # Each probe only finds a witness cell. The proof comes from its
            # exact rational ALL-TIME shadow interval, never from the probe.
            def merged():
                merged=[]
                for lo,hi in sorted(shadows):
                    lo=max(Fraction(0),lo);hi=min(Fraction(1),hi)
                    if lo>hi:continue
                    if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
                    else:merged.append([lo,hi])
                return merged
            certified=False
            for _ in range(64):
                union=merged()
                if len(union)==1 and union[0][0]<=0 and union[0][1]>=1:certified=True;reason="all_time_rational_shadow_union";break
                uncovered=[];last=Fraction(0)
                for lo,hi in union:
                    if lo>last:uncovered.append((last,lo))
                    last=max(last,hi)
                if last<1:uncovered.append((last,Fraction(1)))
                if not uncovered:reason="endpoint_only_uncertainty";break
                lo,hi=max(uncovered,key=lambda pair:pair[1]-pair[0]);probe=float((lo+hi)/2)
                probe_position=(np.array(p0)+(np.array(p1)-p0)*probe).tolist()
                cert=self.los(anchor,probe_position,probe_position)
                cell=cert.get("critical_cell")
                if cell is None or cert.get("min_clearance_m",math.inf)>0:reason="uncovered_time_is_clear_or_boundary_uncertain";break
                row,col=cell
                if (row,col) in seen:reason="same_cell_cannot_close_numeric_boundary_gap";break
                seen.add((row,col));height=float(self.los.terrain[row,col])
                shadow=self.cell_shadow(B,A0,A1,row,col,height)
                if shadow is None:reason="floating_witness_not_exact_rational_shadow";break
                shadows.append(shadow);evidence.append(dict(cell=cell,shadow=[str(t) for t in shadow]))
            result=dict(certified=certified,method=reason,best_blocked_margin_db=best_blocked_margin,witnesses=evidence,
                        covered_intervals=[[str(t) for t in pair] for pair in merged()])
        self.unavailable_cache[key]=result;return result


def communication_check(data,original,nodes,delta_g_db=0.0,clearance_m=0.0,regression_legacy_roundoff=False):
    f=Findings();links=IndependentLinks(original,nodes,delta_g_db,clearance_m,regression_legacy_roundoff)
    service_time_roundoff=1e-7 if regression_legacy_roundoff else 0.0
    tasks={t["id"]:t for t in data.get("tasks",[])};relays={r["id"]:r for r in data.get("relays",[])}
    # Candidate producer names the same declared contract continuous_check.
    c=data.get("communication",data.get("continuous_check",{}));intervals=c.get("intervals",[]);points=c.get("boundary_points",[])
    by_event=defaultdict(list);point_event=defaultdict(list);certs=[];unresolved=[];failed=[];backhaul={};priority_unresolved=[]
    for rid,r in relays.items():
        proof=links.certify(links.gateway,r["position"],r["position"],"backhaul",point=True)
        backhaul[rid]=proof
        if proof["status"]!="certified":(failed if proof["status"]=="failed" else unresolved).append(dict(relay=rid,link="backhaul",proof=proof))
    for row in intervals:by_event[row.get("task"),row.get("event")].append(row)
    for row in points:point_event[row.get("task"),row.get("event")].append(row)
    f.require(not c.get("failures",[]),"communication","Production output already records communication failures")
    def point_on(e,seconds):
        duration=e["end"]-e["start"];t=(seconds-e["start"])/duration if duration else 0
        return (np.array(e["p0"])+(np.array(e["p1"])-e["p0"])*t).tolist()
    def check_row(row,e,ispoint):
        lo=row["time"] if ispoint else row["start"];hi=lo if ispoint else row["end"]
        p0,p1=point_on(e,lo),point_on(e,hi);mode=row.get("mode");rid=row.get("relay","")
        where=f"{row.get('task')}.event{row.get('event')}.{lo:.9f}"
        f.require(mode in ["direct","relay","direct_else_relay"],where,"Communication outage or unknown mode")
        if mode=="direct":proof=links.certify(links.gateway,p0,p1,"direct",point=ispoint)
        elif mode in ["relay","direct_else_relay"]:
            f.require(rid in relays,where,"Unknown relay assignment")
            if rid not in relays:return
            r=relays[rid]
            f.require(r["service_start"]<=lo+service_time_roundoff and hi<=r["service_end"]+service_time_roundoff,where,"Relay assigned outside service interval")
            f.require(r["ready"]<=lo+service_time_roundoff,where,"Relay assigned before completion of link establishment")
            proof=links.certify(r["position"],p0,p1,"access",point=ispoint)
            if mode=="relay":
                direct=links.certify(links.gateway,p0,p1,"direct",point=ispoint)
                if direct["status"]=="certified":f.require(False,where,"Relay selected although direct communication is independently guaranteed")
                else:
                    unavailability=links.certify_unavailable(links.gateway,p0,p1,"direct",point=ispoint)
                    if not unavailability["certified"]:priority_unresolved.append(dict(where=where,task=row["task"],event=row["event"],start=lo,end=hi,point=ispoint,note="Direct-unavailability priority not independently certified",direct=direct,unavailability=unavailability))
            else:
                f.require(c.get("policy")=="direct_first_else_bound_relay",where,"Conditional mode needs explicit direct-first policy contract")
        else:return
        rec=dict(task=row["task"],event=row["event"],start=lo,end=hi,point=ispoint,mode=mode,relay=rid,proof=proof)
        certs.append(rec)
        if proof["status"]!="certified":(failed if proof["status"]=="failed" else unresolved).append(rec)
    expected_events=set()
    for tid,task in tasks.items():
        for index,e in enumerate(task["events"]):
            if "p0" not in e:continue
            key=(tid,index);expected_events.add(key);rows=sorted(by_event[key],key=lambda r:(r["start"],r["end"]));pnts=point_event[key]
            f.require(bool(rows),f"{tid}.{index}","Missing phase interval coverage")
            if not rows:continue
            f.close(rows[0]["start"],e["start"],f"{tid}.{index}.first_coverage");f.close(rows[-1]["end"],e["end"],f"{tid}.{index}.last_coverage")
            for r in rows:
                f.require(e["start"]-1e-7<=r["start"]<=r["end"]<=e["end"]+1e-7,f"{tid}.{index}","Invalid interval range")
            for a,b in zip(rows,rows[1:]):f.close(a["end"],b["start"],f"{tid}.{index}.partition")
            boundaries={e["start"],e["end"],*[x for r in rows for x in [r["start"],r["end"]]]}
            for t in boundaries:f.require(any(abs(p["time"]-t)<=1e-7 for p in pnts),f"{tid}.{index}.{t}","Missing explicit boundary-point verification")
            for r in rows:check_row(r,e,False)
            for r in pnts:
                f.require(e["start"]-1e-7<=r["time"]<=e["end"]+1e-7,f"{tid}.{index}","Boundary point beyond phase")
                check_row(r,e,True)
    f.require(set(by_event)<=expected_events,"communication","Unknown task/event interval")
    f.require(set(point_event)<=expected_events,"communication","Unknown task/event boundary point")
    margins=[r["proof"]["margin_lower_db"] for r in certs if "margin_lower_db" in r["proof"]]
    return dict(all_selected_links_independently_certified=not failed and not unresolved and not f.errors,
                direct_priority_independently_certified=not priority_unresolved and not f.errors,
                acceptance=dict(delta_g_db=delta_g_db,clearance_m=clearance_m,budget_roundoff_db=links.budget_roundoff_db,
                                service_time_roundoff_s=service_time_roundoff,
                                los_additional_positive_guard_m=1e-8),
                interval_count=len(intervals),boundary_point_count=len(points),
                min_gate_surplus_db=min(margins,default=None),
                min_nominal_budget_margin_db=(min(margins)+delta_g_db) if margins else None,
                errors=f.errors,failed=failed,unresolved=unresolved,priority_unresolved=priority_unresolved,
                comparison_count=f.comparisons,backhaul=backhaul,certificates=certs,budgets_db=links.p["limits"],
                proof_source="src/independent_triangle_los.py",proof_source_sha256=hashlib.sha256(LOS_SOURCE.read_bytes()).hexdigest(),
                limitation="Open interval closures may touch terrain: unresolved cases are retained, never inferred from finite samples.")





if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
