from __future__ import annotations
import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import numpy as np
import tifffile

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
G = 9.80665


def sheet(path: Path, number=1):
    with ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            strings = ["".join(x.itertext()) for x in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        doc = ET.fromstring(z.read(f"xl/worksheets/sheet{number}.xml"))
        cells = {}
        for cell in doc.findall(".//s:c", NS):
            value = cell.find("s:v", NS)
            if value is None:
                value = "".join(cell.itertext())
            else:
                value = strings[int(value.text)] if cell.get("t") == "s" else value.text
            cells[cell.get("r")] = value
        return cells


def read_originals(root: Path):
    nodefile = next(root.rglob("调度中心与服务区.xlsx"))
    c = sheet(nodefile)
    nodes = {}
    for r in [3, *range(7, 22)]:
        key = c[f"A{r}"]
        nodes[key] = {"id": key, "lon": float(c[f"C{r}"]), "lat": float(c[f"D{r}"]),
                      "ground_m": float(c[f"E{r}"])}
        nodes[key]["operation_m"] = nodes[key]["ground_m"] + (0 if key == "O01" else 30)
    aircraft = next(root.rglob("运输无人机数据.xlsx"))
    c = sheet(aircraft)
    fields = {"C": "empty_mass_kg", "D": "max_payload_kg", "E": "volume_m3", "F": "cruise_mps",
              "G": "empty_range_m", "H": "full_range_m", "I": "usable_kwh", "J": "reserve_pct",
              "K": "preparation_s", "L": "load_per_box_s", "M": "handover_base_s",
              "N": "handover_per_box_s", "O": "climb_mps", "P": "descent_mps", "Q": "climb_eta"}
    models = {c[f"A{r}"]: {name: float(c[f"{col}{r}"]) for col, name in fields.items()}
              for r in range(3, 6)}
    for r in range(20, 23):
        models[c[f"A{r}"]].update(battery_count=int(c[f"B{r}"]), full_charge_s=float(c[f"C{r}"]))
    entities = {c[f"A{r}"]: c[f"B{r}"] for r in range(9, 17)}
    demandfile = next(root.rglob("物资需求与配送时限.xlsx"))
    c = sheet(demandfile, 2)
    boxes = {}
    for r in range(2, 82):
        key = c[f"A{r}"]
        first = c[f"F{r}"] == "是"
        boxes[key] = {"id": key, "service": c[f"B{r}"], "type": c[f"C{r}"],
                      "mass_kg": float(c[f"D{r}"]), "volume_m3": float(c[f"E{r}"]),
                      "first": first, "first_deadline_s": float(c[f"G{r}"]) if first else None,
                      "expected_s": float(c[f"H{r}"]), "priority": float(c[f"I{r}"])}
    return nodes, models, entities, boxes


def clipped_cells(p, q, shape):
    """All closed unit grid cells touching [p,q], via independent rectangle clipping."""
    x0, y0 = p
    dx, dy = q[0]-x0, q[1]-y0
    eps = 1e-10
    cols = np.arange(max(0, math.ceil(min(x0, q[0])-1-eps)),
                     min(shape[1]-1, math.floor(max(x0, q[0])+eps))+1)
    rows = np.arange(max(0, math.ceil(min(y0, q[1])-1-eps)),
                     min(shape[0]-1, math.floor(max(y0, q[1])+eps))+1)
    rr, cc = np.meshgrid(rows, cols, indexing="ij")
    lo = np.zeros(rr.shape)
    hi = np.ones(rr.shape)
    for start, delta, lower in [(x0, dx, cc), (y0, dy, rr)]:
        if abs(delta) < 1e-15:
            hi = np.where((start >= lower-eps) & (start <= lower+1+eps), hi, -1)
        else:
            t1 = (lower-start)/delta
            t2 = (lower+1-start)/delta
            lo = np.maximum(lo, np.minimum(t1, t2))
            hi = np.minimum(hi, np.maximum(t1, t2))
    keep = lo <= hi+eps
    return np.column_stack((rr[keep], cc[keep]))


class Terrain:
    def __init__(self, path):
        with tifffile.TiffFile(path) as tif:
            page = tif.pages[0]
            self.dem = page.asarray()
            self.tie = tuple(page.tags[33922].value)
            self.scale = tuple(page.tags[33550].value)
            self.geokeys = tuple(page.tags[34735].value)
        keys = {self.geokeys[i]: self.geokeys[i+3] for i in range(4, len(self.geokeys), 4)}
        assert keys[1025] == 2, "The half-cell correction is only valid for PixelIsPoint"
        self.west = self.tie[3] - self.scale[0]/2
        self.north = self.tie[4] + self.scale[1]/2

    def pixel(self, node):
        return ((node["lon"]-self.west)/self.scale[0], (self.north-node["lat"])/self.scale[1])

    def segment(self, a, b):
        p, q = self.pixel(a), self.pixel(b)
        h, w = self.dem.shape
        assert all(0 <= x <= w and 0 <= y <= h for x, y in (p, q)), "Endpoint beyond DEM"
        cells = clipped_cells(p, q, self.dem.shape)
        heights = self.dem[cells[:, 0], cells[:, 1]]
        assert len(heights), "No terrain cells"
        assert np.isfinite(heights).all() and not np.any(heights == -32767), "NoData on segment"
        idx = int(np.argmax(heights))
        return {"max_ground_m": float(heights[idx]), "cell_count": len(cells),
                "max_cell_row_col": cells[idx].tolist(),
                "cell_set_sha256": hashlib.sha256(cells.astype("<i8").tobytes()).hexdigest()}


def local_distance(a, b, origin):
    semimajor = 6378137.0
    eccentricity_sq = (1/298.257223563)*(2-1/298.257223563)
    phi = math.radians(origin["lat"])
    w = math.sqrt(1-eccentricity_sq*math.sin(phi)**2)
    n = semimajor/w
    m = semimajor*(1-eccentricity_sq)/w**3
    return math.hypot(math.radians(b["lon"]-a["lon"])*n*math.cos(phi),
                      math.radians(b["lat"]-a["lat"])*m)


def vincenty_distance(a, b):
    """WGS84 inverse geodesic, local non-antipodal cases; no new external package."""
    major = 6378137.0
    f = 1/298.257223563
    minor = major*(1-f)
    u1 = math.atan((1-f)*math.tan(math.radians(a["lat"])))
    u2 = math.atan((1-f)*math.tan(math.radians(b["lat"])))
    su1, cu1, su2, cu2 = math.sin(u1), math.cos(u1), math.sin(u2), math.cos(u2)
    delta = math.radians(b["lon"]-a["lon"])
    lam = delta
    for _ in range(100):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.hypot(cu2*sl, cu1*su2-su1*cu2*cl)
        if ss == 0: return 0.0
        cs = su1*su2+cu1*cu2*cl
        sigma = math.atan2(ss, cs)
        sa = cu1*cu2*sl/ss
        ca2 = 1-sa*sa
        c2sm = cs-2*su1*su2/ca2 if ca2 > 1e-15 else 0
        c = f/16*ca2*(4+f*(4-3*ca2))
        old = lam
        lam = delta+(1-c)*f*sa*(sigma+c*ss*(c2sm+c*cs*(-1+2*c2sm*c2sm)))
        if abs(lam-old) < 1e-13: break
    else: raise RuntimeError("Vincenty did not converge")
    u2p = ca2*(major*major-minor*minor)/(minor*minor)
    aa = 1+u2p/16384*(4096+u2p*(-768+u2p*(320-175*u2p)))
    bb = u2p/1024*(256+u2p*(-128+u2p*(74-47*u2p)))
    ds = bb*ss*(c2sm+bb/4*(cs*(-1+2*c2sm*c2sm)-bb/6*c2sm*(-3+4*ss*ss)*(-3+4*c2sm*c2sm)))
    return minor*aa*(sigma-ds)


def leg_values(model, leg, load):
    assert -1e-8 <= load <= model["max_payload_kg"]+1e-8
    effective_range = model["empty_range_m"]-(model["empty_range_m"]-model["full_range_m"])*(load/model["max_payload_kg"])**1.5
    climb_s = leg["climb_m"]/model["climb_mps"]
    cruise_s = leg["distance_m"]/model["cruise_mps"]
    descent_s = leg["descent_m"]/model["descent_mps"]
    horizontal = model["usable_kwh"]*leg["distance_m"]/effective_range
    climb = (model["empty_mass_kg"]+load)*G*leg["climb_m"]/(model["climb_eta"]*3.6e6)
    return dict(load_kg=load, range_m=effective_range, climb_s=climb_s, cruise_s=cruise_s,
                descent_s=descent_s, flight_s=climb_s+cruise_s+descent_s,
                horizontal_kwh=horizontal, climb_kwh=climb, energy_kwh=horizontal+climb)


def charge_seconds(soc, full_s):
    assert -1e-9 <= soc <= 1+1e-9
    return full_s*(.65*(.9-soc)/.9+.35) if soc < .9 else full_s*.35*(1-soc)/.1


def small_tests():
    cases = [((.5, .5), (2.5, .5), {(0,0),(0,1),(0,2)}),
             ((.5,1), (2.5,1), {(r,c) for r in (0,1) for c in (0,1,2)}),
             ((.5,.5), (2.5,2.5), {(0,0),(0,1),(1,0),(1,1),(1,2),(2,1),(2,2)}),
             ((1,1), (1,1), {(0,0),(0,1),(1,0),(1,1)}),
             ((1,.5), (1,2.5), {(r,c) for r in (0,1,2) for c in (0,1)})]
    for p, q, expected in cases:
        actual = set(map(tuple, clipped_cells(p,q,(4,4))))
        assert actual == expected, (p,q,actual,expected)
        assert set(map(tuple, clipped_cells(q,p,(4,4)))) == expected
    assert abs(charge_seconds(.9,1800)-630) < 1e-9
    assert abs(charge_seconds(.2,1800)-1540) < 1e-9
    assert charge_seconds(1,1800) == 0
    return {"closed_pixel_geometry_cases": len(cases), "charge_cases": 3, "passed": True}


def audit(root, out):
    nodes, models, entities, boxes = read_originals(root)
    terrain_file = next(root.rglob("*.tif"))
    terrain = Terrain(terrain_file)
    legs = {}
    for aid, a in nodes.items():
        for bid, b in nodes.items():
            if aid == bid: continue
            leg = terrain.segment(a,b)
            leg.update(from_node=aid,to_node=bid,distance_m=local_distance(a,b,nodes["O01"]),
                       geodesic_m=vincenty_distance(a,b),cruise_altitude_m=leg["max_ground_m"]+50)
            leg["climb_m"] = leg["cruise_altitude_m"]-a["operation_m"]
            leg["descent_m"] = leg["cruise_altitude_m"]-b["operation_m"]
            assert min(leg["climb_m"],leg["descent_m"]) >= 0
            legs[f"{aid}->{bid}"] = leg
    for key, leg in legs.items():
        reverse = legs[f"{leg['to_node']}->{leg['from_node']}"]
        assert leg["cell_set_sha256"] == reverse["cell_set_sha256"]
    capacities = []
    for gid, g in models.items():
        for sid in nodes:
            if sid == "O01": continue
            back = leg_values(g, legs[f"{sid}->O01"], 0)["energy_kwh"]
            limit = g["usable_kwh"]*(1-g["reserve_pct"]/100)
            energy = lambda q: leg_values(g, legs[f"O01->{sid}"], q)["energy_kwh"]+back
            lo, hi = 0.0, g["max_payload_kg"]
            if energy(0)>limit: maxload = None
            elif energy(hi)<=limit: maxload = hi
            else:
                for _ in range(70):
                    mid=(lo+hi)/2
                    if energy(mid)<=limit: lo=mid
                    else: hi=mid
                maxload=lo
            capacities.append(dict(model=gid,service=sid,max_safe_payload_kg=maxload,
                                   energy_at_safe_payload_kwh=energy(maxload) if maxload is not None else None))
    # Two real-data examples independently recomputed, no solver-produced feasible flags.
    examples=[]
    for gid, stops in [("A",[("S001",["S001-MED-01","S001-WAT-01"])]),
                        ("C",[("S001",["S001-MED-01","S001-WAT-01"]),("S002",["S002-MED-01","S002-WAT-01"])])]:
        g=models[gid]
        ids=[b for _,bs in stops for b in bs]
        load=sum(boxes[b]["mass_kg"] for b in ids)
        clock=g["preparation_s"]+len(ids)*g["load_per_box_s"]
        e=0; records=[]; prev="O01"
        for sid,bs in [*stops,("O01",[])]:
            leg=leg_values(g,legs[f"{prev}->{sid}"],load)
            start=clock; clock+=leg["flight_s"]; arrival=clock
            handover=g["handover_base_s"]+len(bs)*g["handover_per_box_s"] if bs else 0
            clock+=handover; e+=leg["energy_kwh"]
            records.append(dict(from_node=prev,to_node=sid,depart_s=start,arrival_s=arrival,complete_s=clock,
                                handover_s=handover,boxes=bs,**leg))
            load-=sum(boxes[b]["mass_kg"] for b in bs); prev=sid
        examples.append(dict(model=gid,boxes=ids,initial_mass_kg=sum(boxes[b]["mass_kg"] for b in ids),
                             initial_volume_m3=sum(boxes[b]["volume_m3"] for b in ids),legs=records,
                             return_s=clock,energy_kwh=e,remaining_soc=1-e/g["usable_kwh"],
                             recharge_s=charge_seconds(1-e/g["usable_kwh"],g["full_charge_s"])))
    maxabs=max(legs.values(),key=lambda x:abs(x["distance_m"]-x["geodesic_m"]))
    maxrel=max(legs.values(),key=lambda x:abs(x["distance_m"]/x["geodesic_m"]-1))
    result=dict(version="independent-20260923-v1",tests=small_tests(),
                original_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in [terrain_file,*root.rglob("*.xlsx")]},
                inputs=dict(node_count=len(nodes),box_count=len(boxes),total_mass_kg=sum(b["mass_kg"] for b in boxes.values()),
                            total_volume_m3=sum(b["volume_m3"] for b in boxes.values()),
                            first_boxes=sum(b["first"] for b in boxes.values()),medical_boxes=sum(b["type"]=="医疗物资" for b in boxes.values())),
                dem=dict(shape=terrain.dem.shape,tiepoint=terrain.tie,scale=terrain.scale,geokeys=terrain.geokeys,
                         pixel_is_point=True,west_boundary=terrain.west,north_boundary=terrain.north),
                projection_check=dict(method="WGS84 O01 fixed M,N projection versus independent Vincenty inverse",
                                      largest_absolute_error_m=abs(maxabs["distance_m"]-maxabs["geodesic_m"]),
                                      largest_absolute_pair=[maxabs["from_node"],maxabs["to_node"]],
                                      largest_relative_error_pct=100*abs(maxrel["distance_m"]/maxrel["geodesic_m"]-1),
                                      largest_relative_pair=[maxrel["from_node"],maxrel["to_node"]]),
                assumptions=["水平能耗 Euse*d/L(q) 与爬升能耗 (m0+q)*9.80665*h/(eta*3.6e6) 为待核推导口径。",
                             "交接未增加未给定功率对应的悬停能耗；不添加运输换电或周转时长。",
                             "节点地面高程用原 XLSX；地形逐像元最高值加 50 m，PixelIsPoint 半像元平移。",
                             "边界接触像元保守纳入；距离使用 O01 纬度 WGS84 局部线性投影。",
                             "此审查不证明通信连续性或 Q1/Q2 全局最优，不是完整方案。"],
                legs=legs,q1_capacities=capacities,examples=examples)
    out.mkdir(parents=True,exist_ok=True)
    (out/"independent_common_results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    with (out/"independent_terrain_240legs.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=list(next(iter(legs.values())).keys()))
        writer.writeheader();writer.writerows(legs.values())
    with (out/"independent_q1_45capacities.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=list(capacities[0]));writer.writeheader();writer.writerows(capacities)
    return result



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
