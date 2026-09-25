"""F8 问题四不可拆单元关系图：(a) 主口径（跨组中继整任务复制）14 个单元；(b) 禁止复制口径 4 个单元。

节点为原题 15 个服务区（经纬度）。实线：同一运输架次访问的服务区（Q3-M002：S001—S005）；
虚线：中继任务（画在其悬停点）与它保障的服务区相连，共用同一中继的服务区因此经该中继节点相通。保障关系取
results/q3.json communication 中带中继编号的全部区间与边界点（共 25 对“任务—中继”，其中 3 对只作备用、
在标称状态 nominal_communication 中未实际使用，画为点线）。
单元划分与 results/q4.json、results/q4_no_copy_sensitivity.json 的 components 逐项核对。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import math
from collections import defaultdict
from itertools import combinations
import numpy as np
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon
from scipy.spatial import ConvexHull

STEM = "fig_q4_units"
UNIT_COL = ["#0072B2", "#E69F00", "#009E73", "#CC79A7"]
PAIR_COL = "#D55E00"
RELAY_OFFSET = {"R-001": (7, 3), "R-002": (-5, -9), "R-003": (7, -9), "R-004": (7, 7), "R-005": (-6, 2)}
LABEL_OFFSET = {"S001": (7, -4), "S002": (6, 5), "S003": (-7, 6), "S004": (6, 5), "S005": (-6, -9),
                "S006": (-6, -11), "S007": (-6, -11), "S008": (6, 5), "S009": (6, 5), "S010": (-7, -7),
                "S011": (-7, 6), "S012": (6, 5), "S013": (6, 5), "S014": (6, -10), "S015": (-7, 6)}


def union_find(sites, groups):
    parent = {s: s for s in sites}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for g in groups:
        g = sorted(g)
        for x in g[1:]:
            parent[find(x)] = find(g[0])
    out = defaultdict(list)
    for s in sites:
        out[find(s)].append(s)
    return sorted((sorted(v) for v in out.values()), key=lambda v: v[0])


def hull_patch(pts, pad, kx, ky, **kw):
    """以各点为圆心、半径 pad（m）的圆的凸包，用于表示同一单元。"""
    ang = np.linspace(0, 2 * np.pi, 48, endpoint=False)
    cloud = np.array([(x + pad * math.cos(a) / kx, y + pad * math.sin(a) / ky) for x, y in pts for a in ang])
    h = ConvexHull(cloud)
    return Polygon(cloud[h.vertices], closed=True, **kw)


def main():
    fk.setup()
    L = fk.labels()["F08"]
    p3, p4, p4n = fk.RESULTS / "q3.json", fk.RESULTS / "q4.json", fk.RESULTS / "q4_no_copy_sensitivity.json"
    q3, q4, q4n = fk.load_json(p3), fk.load_json(p4), fk.load_json(p4n)
    nodes = fk.nodes()
    sites = sorted(k for k in nodes if k != "O01")
    tasks = {t["id"]: t for t in q3["tasks"]}
    comm, nom = q3["communication"], q3["nominal_communication"]
    pairs = {(r["task"], r["relay"]) for r in comm["intervals"] + comm["boundary_points"] if r.get("relay")}
    used = {(r["task"], r["relay"]) for r in nom["intervals"] + nom["boundary_points"]
            if r.get("relay") and r.get("mode") != "direct"}
    assert len(pairs) == 25 and used <= pairs and len(used) == 22
    backup = sorted(pairs - used)

    multi = [t["order"] for t in tasks.values() if len(t["order"]) > 1]
    serve_all = defaultdict(set)
    edge_kind = {}
    for t, r in sorted(pairs):
        serve_all[r].update(tasks[t]["order"])
        for site in tasks[t]["order"]:
            k = "used" if (t, r) in used else "backup"
            if edge_kind.get((r, site)) != "used":
                edge_kind[(r, site)] = k
    e_route = {tuple(sorted(e)) for o in multi for e in combinations(sorted(o), 2)}
    relays = {r["id"]: r for r in q3["relays"]}
    pos_ids = defaultdict(list)          # 同一悬停点上的中继任务合并标注
    for rid, r in sorted(relays.items()):
        pos_ids[(round(r["position"][0], 9), round(r["position"][1], 9))].append(rid)

    units_main = union_find(sites, multi)
    units_nc = union_find(sites, multi + [sorted(v) for v in serve_all.values()])
    assert units_main == sorted(sorted(c) for c in q4["components"])
    assert units_nc == sorted(sorted(c) for c in q4n["components"])
    assert len(units_main) == 14 and len(units_nc) == 4

    lons = [nodes[s]["lon"] for s in sites] + [r["position"][0] for r in relays.values()]
    lats = [nodes[s]["lat"] for s in sites] + [r["position"][1] for r in relays.values()]
    lat_mid = (min(lats) + max(lats)) / 2
    kx, ky = fk.local_scale(lat_mid)
    x0, x1 = min(lons) - 0.010, max(lons) + 0.012
    y0, y1 = min(lats) - 0.008, max(lats) + 0.008
    fig, axes = plt.subplots(1, 2, figsize=(fk.FULL_W, 7.4 * fk.CM), layout="constrained")
    xy = lambda s: (nodes[s]["lon"], nodes[s]["lat"])
    rows = []
    for ax, units, tag, title in [(axes[0], units_main, "(a)", L["main"]), (axes[1], units_nc, "(b)", L["no_copy"])]:
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect(1 / math.cos(math.radians(lat_mid)))
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(True)
            sp.set_color(fk.C["grid"])
        colour = {}
        for u in units:
            if len(units) == 4:
                col = UNIT_COL[units.index(u)]
            elif len(u) > 1:
                col = PAIR_COL
            else:
                continue
            if len(u) > 1:
                ax.add_patch(hull_patch([xy(s) for s in u], 520, kx, ky, fc=col, alpha=0.16, ec=col, lw=0.8, zorder=1))
            for s in u:
                colour[s] = col
        for (r, site), k in sorted(edge_kind.items()):
            pr = relays[r]["position"][:2]
            ax.plot(*zip(pr, xy(site)), color=fk.C["relay"], lw=0.8 if k == "used" else 1.0,
                    ls=(0, (4, 2)) if k == "used" else (0, (1, 1.4)), alpha=0.85, zorder=2)
        for (lo, la), ids in pos_ids.items():
            ax.scatter(lo, la, marker="D", s=26, color=fk.C["relay"], edgecolor="white", linewidth=0.5, zorder=4)
            dx, dy = RELAY_OFFSET[ids[0]]
            ax.annotate("R-" + "/".join(i[2:] for i in ids), (lo, la), xytext=(dx, dy), textcoords="offset points",
                        fontsize=10, color=fk.C["relay"], ha="left" if dx >= 0 else "right", va="center", zorder=6,
                        bbox=dict(boxstyle="round,pad=0.05", fc="white", ec="none", alpha=0.7))
        for a, b in sorted(e_route):
            ax.plot(*zip(xy(a), xy(b)), color=fk.C["ink"], lw=2.0, zorder=3)
        for s in sites:
            ax.scatter(*xy(s), s=36, facecolor=colour.get(s, "white"), edgecolor=fk.C["ink"], linewidth=0.8, zorder=5)
            dx, dy = LABEL_OFFSET[s]
            ax.annotate(s, xy(s), xytext=(dx, dy), textcoords="offset points", fontsize=10,
                        ha="left" if dx >= 0 else "right", va="center", zorder=6,
                        bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.7))
        ax.text(0.0, 1.015, f"{tag} {title}：{len(units)} {L['units']}", transform=ax.transAxes, ha="left",
                va="bottom", fontsize=10.5)
        for k, u in enumerate(units):
            rows.append({"panel": tag.strip("()"), "unit": k + 1, "sites": " ".join(u), "size": len(u)})
    fk.scale_bar(axes[0], lat_mid, km=2, x0=0.04, y0=0.90)
    for a, b in sorted(e_route):
        rows.append({"panel": "edge", "edge_kind": "same_sortie", "site_a": a, "site_b": b})
    for (r, site), k in sorted(edge_kind.items()):
        rows.append({"panel": "edge", "edge_kind": f"relay_{k}", "relay": r, "site_a": site,
                     "lon": relays[r]["position"][0], "lat": relays[r]["position"][1]})
    for t, r in sorted(pairs):
        rows.append({"panel": "pair", "edge_kind": "backup" if (t, r) in backup else "used", "task": t, "relay": r,
                     "sites": " ".join(tasks[t]["order"])})
    for s in sites:
        rows.append({"panel": "node", "site_a": s, "lon": nodes[s]["lon"], "lat": nodes[s]["lat"]})
    handles = [Line2D([], [], color=fk.C["ink"], lw=2.0, label=L["same_sortie"]),
               Line2D([], [], marker="D", ls=(0, (4, 2)), color=fk.C["relay"], lw=0.8, markersize=4.5,
                      mec="white", label=L["shared_relay"]),
               Line2D([], [], color=fk.C["relay"], lw=1.0, ls=(0, (1, 1.4)), label=L["backup"]),
               Patch(fc=PAIR_COL, alpha=0.3, ec=PAIR_COL, label=L["multi_unit"])]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, columnspacing=1.2, handletextpad=0.4)
    fk.write_csv(HERE / f"{STEM}.csv", rows, ["panel", "unit", "sites", "size", "edge_kind", "site_a", "site_b",
                                              "task", "relay", "lon", "lat"])
    fk.save(fig, HERE, STEM, figure_id="F8",
            caption="问题四不可拆单元：(a) 跨组中继整任务复制（14 个单元）；(b) 禁止复制（4 个单元）",
            section="9.2.1 或 9.5.1",
            sources=[p3, p4, p4n, fk.NODE_XLSX],
            key_values={"units_main": units_main, "units_no_copy": units_nc,
                        "task_relay_pairs": len(pairs), "used_pairs": len(used), "backup_pairs": [list(x) for x in backup],
                        "same_sortie_edges": sorted(e_route),
                        "relay_site_links_used": sum(1 for k in edge_kind.values() if k == "used"),
                        "relay_site_links_backup_only": sorted(f"{r}-{s}" for (r, s), k in edge_kind.items() if k == "backup"),
                        "relay_serves": {r: sorted(v) for r, v in sorted(serve_all.items())}},
            notes="实线为同一运输架次访问的服务区；紫色菱形为中继任务的悬停点（标注中继任务编号，同一点位的任务合并标注），"
                  "虚线连向它实际保障的服务区，点线为只作备用的保障关系；共用同一中继的服务区经该菱形相通。"
                  "(a) 中继任务可跨组复制，只有同一架次把 S001 与 S005 绑成一个单元，其余 13 个服务区各自成单元；"
                  "(b) 不允许复制时，共用中继的服务区必须同组，合并为 4 个单元（色块）。")


if __name__ == "__main__":
    main()
