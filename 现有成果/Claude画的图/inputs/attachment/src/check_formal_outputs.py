from __future__ import annotations
import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from independent_check import audit, read_originals, leg_values, charge_seconds


class Findings:
    def __init__(self):
        self.errors=[]
        self.comparisons=0
    def require(self, yes, where, message):
        self.comparisons+=1
        if not yes: self.errors.append({"where":where,"message":message})
    def close(self, found, expected, where, tolerance=1e-6):
        ok=isinstance(found,(int,float)) and math.isfinite(found) and abs(found-expected)<=max(tolerance,1e-10*abs(expected))
        self.require(ok,where,f"reported={found!r}; independent={expected!r}")


def compare_common(run, common):
    f=Findings()
    p=run/"航段几何_240.csv"
    if not p.exists(): return {"available":False}
    with p.open(encoding="utf-8-sig",newline="") as stream: rows=list(csv.DictReader(stream))
    f.require(len(rows)==240,str(p.name),"Expected 240 directed legs")
    mapping={"distance":"distance_m","terrain_max":"max_ground_m","cruise_z":"cruise_altitude_m",
             "up":"climb_m","down":"descent_m","cells":"cell_count"}
    for row in rows:
        key=row["from_node"]+"->"+row["to_node"]
        for official,independent in mapping.items():
            f.close(float(row[official]),common["legs"][key][independent],key+"."+official)
    p=run/"Q1_45组安全载荷.csv"
    if p.exists():
        with p.open(encoding="utf-8-sig",newline="") as stream: rows=list(csv.DictReader(stream))
        f.require(len(rows)==45,p.name,"Expected 45 model-site maximum payloads")
        caps={(r["model"],r["service"]):r["max_safe_payload_kg"] for r in common["q1_capacities"]}
        for row in rows:
            f.close(float(row["payload"]),caps[row["type"],row["site"]],"maxload."+row["type"]+"."+row["site"])
    return {"available":True,"passed":not f.errors,"comparison_count":f.comparisons,"errors":f.errors}


def check_solution(data, kind, nodes, models, entities, boxes, common):
    f=Findings()
    seen=Counter(); taskids=[]; drone_intervals=defaultdict(list); battery_intervals=defaultdict(list)
    used_battery=defaultdict(set); deliveries={}; energy=0; total_duration=0; return_times=[]
    first_margins=[]; medical_margins=[]; records=[]
    tasks=data.get("tasks",[])
    f.require(bool(tasks),kind,"No tasks")
    for ix, task in enumerate(tasks):
        tid=task.get("id",f"task-{ix}"); taskids.append(tid)
        gid=task.get("type"); ids=task.get("boxes",[]); order=task.get("order",[])
        f.require(gid in models,tid,"Unknown model")
        f.require(bool(ids),tid,"Empty box list")
        f.require(all(b in boxes for b in ids),tid,"Unknown box")
        f.require(all(s in nodes and s!="O01" for s in order),tid,"Unknown service node")
        if gid not in models or any(b not in boxes for b in ids) or any(s not in nodes for s in order): continue
        g=models[gid]; seen.update(ids)
        f.require(len(set(ids))==len(ids),tid,"Repeated box within task")
        f.require(len(set(order))==len(order),tid,"Repeated service visit: contract only permits one delivery occurrence per listed site")
        f.require(set(order)=={boxes[b]["service"] for b in ids},tid,"Route nodes disagree with assigned boxes")
        if kind=="Q1": f.require(len(order)==1,tid,"Q1 must be single-service round trip")
        mass=sum(boxes[b]["mass_kg"] for b in ids); volume=sum(boxes[b]["volume_m3"] for b in ids)
        f.close(task.get("mass"),mass,tid+".mass");f.close(task.get("volume"),volume,tid+".volume")
        f.require(mass<=g["max_payload_kg"]+1e-8,tid,"Mass exceeds model capacity")
        f.require(volume<=g["volume_m3"]+1e-10,tid,"Volume exceeds model capacity")
        start=task.get("start",0) if kind=="Q2" else 0
        f.require(start>=0,tid,"Negative start time")
        prep=g["preparation_s"]+len(ids)*g["load_per_box_s"]
        expected_events=[dict(phase="准备装载",start=start,end=start+prep,node="O01")]
        clock=start+prep; prev="O01"; payload=mass; taskenergy=0; expected_deliveries={}
        reported_legs=task.get("legs",[])
        f.require(len(reported_legs)==len(order)+1,tid,"Wrong leg count")
        for j,sid in enumerate([*order,"O01"]):
            key=f"{prev}->{sid}"
            if key not in common["legs"]: f.require(False,tid,"Degenerate or unknown leg "+key); continue
            geo=common["legs"][key]
            if not -1e-8<=payload<=g["max_payload_kg"]+1e-8: break
            val=leg_values(g,geo,payload)
            expected={"payload":payload,"distance":geo["distance_m"],"terrain_max":geo["max_ground_m"],
                      "cruise_z":geo["cruise_altitude_m"],"up":geo["climb_m"],"down":geo["descent_m"],
                      "cells":geo["cell_count"],"time":val["flight_s"],"energy":val["energy_kwh"],
                      "horizontal_energy":val["horizontal_kwh"],"up_energy":val["climb_kwh"],"range":val["range_m"]}
            if j<len(reported_legs):
                leg=reported_legs[j]
                f.require(leg.get("from_node")==prev and leg.get("to_node")==sid,tid+f".leg{j}","Wrong endpoint/order")
                for field,number in expected.items(): f.close(leg.get(field),number,tid+f".leg{j}."+field)
            a=nodes[prev];b=nodes[sid];z=geo["cruise_altitude_m"]
            points=[[a["lon"],a["lat"],a["operation_m"]],[a["lon"],a["lat"],z],
                    [b["lon"],b["lat"],z],[b["lon"],b["lat"],b["operation_m"]]]
            for n,(phase,duration) in enumerate([("爬升",val["climb_s"]),("巡航",val["cruise_s"]),("下降",val["descent_s"])]):
                expected_events.append(dict(phase=phase,start=clock,end=clock+duration,p0=points[n],p1=points[n+1],from_node=prev,to_node=sid))
                clock+=duration
            taskenergy+=val["energy_kwh"]
            if sid!="O01":
                site_boxes=[b for b in ids if boxes[b]["service"]==sid]
                duration=g["handover_base_s"]+len(site_boxes)*g["handover_per_box_s"]
                expected_events.append(dict(phase="交接",start=clock,end=clock+duration,p0=points[-1],p1=points[-1],node=sid))
                clock+=duration
                for box in site_boxes: expected_deliveries[box]=clock;deliveries[box]=clock
                payload-=sum(boxes[b]["mass_kg"] for b in site_boxes)
            prev=sid
        f.close(payload,0,tid+".return_payload")
        f.close(task.get("duration"),clock-start,tid+".duration")
        f.close(task.get("energy"),taskenergy,tid+".energy")
        soc=1-taskenergy/g["usable_kwh"]
        f.close(task.get("soc"),soc,tid+".soc")
        f.require(soc>=g["reserve_pct"]/100-1e-9,tid,"Return safety energy reserve violated")
        f.require(set(task.get("deliveries",{}))==set(ids),tid,"Delivery keys differ from box IDs")
        for box,completion in expected_deliveries.items():
            f.close(task.get("deliveries",{}).get(box),completion,tid+".delivery."+box)
            if kind=="Q2":
                b=boxes[box]
                if b["first"]:
                    margin=b["first_deadline_s"]-completion;first_margins.append(margin)
                    f.require(margin>=-1e-6,tid+"."+box,"First-batch hard deadline violated")
                if b["type"]=="医疗物资":
                    margin=b["expected_s"]-completion;medical_margins.append(margin)
                    f.require(margin>=-1e-6,tid+"."+box,"Medical hard deadline violated")
        events=task.get("events",[])
        f.require(len(events)==len(expected_events),tid,"Phase timeline length mismatch")
        for j,(actual,expected) in enumerate(zip(events,expected_events)):
            where=tid+f".event{j}"
            for field in ["phase","node","from_node","to_node"]:
                if field in expected: f.require(actual.get(field)==expected[field],where+"."+field,"Wrong phase/node")
            for field in ["start","end"]: f.close(actual.get(field),expected[field],where+"."+field)
            for field in ["p0","p1"]:
                if field in expected:
                    point=actual.get(field,[])
                    f.require(len(point)==3,where+"."+field,"3D point missing")
                    for k,(aa,ee) in enumerate(zip(point,expected[field])):f.close(aa,ee,where+f".{field}[{k}]")
        if kind=="Q2":
            f.close(task.get("return_time"),clock,tid+".return_time")
            drone=task.get("drone");battery=task.get("battery")
            f.require(entities.get(drone)==gid,tid,"Unknown/incompatible physical aircraft")
            f.require(isinstance(battery,str) and battery.startswith(gid+"-"),tid,"Unknown/incompatible battery label")
            if drone in entities: drone_intervals[drone].append((start,clock,tid))
            if isinstance(battery,str):
                used_battery[gid].add(battery)
                ready=clock+charge_seconds(soc,g["full_charge_s"])
                battery_intervals[battery].append((start,ready,tid,clock,soc))
            return_times.append(clock)
        energy+=taskenergy;total_duration+=clock-start
        records.append(dict(task=tid,mass=mass,volume=volume,start=start,return_time=clock,energy=taskenergy,soc=soc))
    f.require(len(taskids)==len(set(taskids)),kind,"Duplicate task IDs")
    f.require(set(seen)==set(boxes),kind,"Missing or extra boxes")
    for box,count in seen.items(): f.require(count==1,kind+"."+box,f"Box occurs {count} times")
    if kind=="Q2":
        for gid,used in used_battery.items(): f.require(len(used)<=models[gid]["battery_count"],gid,"Battery stock exceeded")
        for category,groups in [("aircraft",drone_intervals),("battery_flight_plus_full_recharge",battery_intervals)]:
            for resource,intervals in groups.items():
                intervals.sort()
                for previous,next_item in zip(intervals,intervals[1:]):
                    f.require(previous[1]<=next_item[0]+1e-6,category+"."+resource,
                              f"Conflict {previous[2]} end={previous[1]} and {next_item[2]} start={next_item[0]}")
    metrics=dict(sorties=len(tasks),total_energy_kwh=energy,cumulative_operation_s=total_duration,
                 box_count=sum(seen.values()),missing_boxes=sorted(set(boxes)-set(seen)))
    if kind=="Q2":
        soft=[(key,b) for key,b in boxes.items() if b["type"]!="医疗物资"]
        metrics.update(makespan_s=max(return_times,default=0),
                       min_first_deadline_margin_s=min(first_margins,default=None),min_medical_deadline_margin_s=min(medical_margins,default=None),
                       weighted_other_tardiness_s=sum(b["priority"]*max(0,deliveries.get(key,float("inf"))-b["expected_s"]) for key,b in soft),
                       late_other_boxes=[key for key,b in soft if deliveries.get(key,float("inf"))>b["expected_s"]])
    return dict(passed=not f.errors,comparison_count=f.comparisons,errors=f.errors,metrics=metrics,
                assumptions="H1 provisional energy; resources occupied from preparation; delivery at whole-stop handover completion; no Q3 continuous-communication claim",
                task_recomputations=records,
                aircraft_intervals=dict(drone_intervals),battery_occupied_until_full_intervals=dict(battery_intervals))





if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
