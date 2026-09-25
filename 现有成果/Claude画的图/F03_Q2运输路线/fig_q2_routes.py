"""F3 问题二运输路线图：24 个架次按机型着色，6 条多点路线加粗并标出方向；底图为原题 DEM 山体阴影。

数据：results/q2.json 各架次的访问顺序与机型；原题节点表；原题 DEM。
输出：同名 CSV（全部航段与节点坐标）、PNG、SVG、meta.json。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import math
from collections import defaultdict
import numpy as np
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch

STEM = "fig_q2_routes"
MULTI_SHIFT = 2.6  # 多点路线向飞行方向左侧平移量（点）
# 服务区标签偏移（点），避免与航线和其他标签重叠
LABEL_OFFSET = {"S001": (6, -3), "S002": (6, 4), "S003": (-8, 6), "S004": (6, 4), "S005": (-8, 6),
                "S006": (-6, -12), "S007": (-6, -13), "S008": (6, 4), "S009": (6, 4), "S010": (8, -8),
                "S011": (-8, 6), "S012": (6, 4), "S013": (6, 4), "S014": (6, -12), "S015": (-8, 6)}
ROUTE_LABEL_OFFSET = {"Q2-003": (8, -3), "Q2-008": (-5, 7), "Q2-012": (-5, 7), "Q2-013": (10, 11),
                      "Q2-019": (6, -9), "Q2-020": (-6, -12)}


def main():
    fk.setup()
    L = fk.labels()
    q2p = fk.RESULTS / "q2.json"
    q2 = fk.load_json(q2p)
    nodes = fk.nodes()
    tasks = sorted(q2["tasks"], key=lambda t: t["id"])
    assert len(tasks) == 24 and q2["metrics"]["sorties"] == 24

    # 航段统计：同一无向航段、同一机型的架次数
    pair_count = defaultdict(int)
    multi = []
    rows = []
    for t in tasks:
        seq = ["O01"] + t["order"] + ["O01"]
        for a, b in zip(seq, seq[1:]):
            rows.append({"record": "leg", "task": t["id"], "type": t["type"], "from": a, "to": b,
                         "route_kind": "multi" if len(t["order"]) > 1 else "single",
                         "from_lon": nodes[a]["lon"], "from_lat": nodes[a]["lat"],
                         "to_lon": nodes[b]["lon"], "to_lat": nodes[b]["lat"]})
        if len(t["order"]) == 1:
            pair_count[(t["order"][0], t["type"])] += 1
        else:
            multi.append(t)
    assert len(multi) == 6
    for n in nodes.values():
        rows.append({"record": "node", "task": "", "type": "", "from": n["id"], "to": "",
                     "route_kind": "", "from_lon": n["lon"], "from_lat": n["lat"], "to_lon": "", "to_lat": ""})

    lons = [n["lon"] for n in nodes.values()]
    lats = [n["lat"] for n in nodes.values()]
    lat_mid = (min(lats) + max(lats)) / 2
    x0, x1 = min(lons) - 0.008, max(lons) + 0.010
    y0, y1 = min(lats) - 0.006, max(lats) + 0.007

    dem = fk.DEM()
    sub, extent, _ = dem.window(x0, x1, y0, y1)
    hs = dem.hillshade(sub, lat_mid)

    fig, ax = plt.subplots(figsize=(fk.FULL_W, 11.2 * fk.CM), layout="constrained")
    ax.imshow(0.62 + 0.38 * hs, extent=extent, cmap="gray", vmin=0, vmax=1, interpolation="bilinear",
              zorder=0, origin="upper")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    fk.map_axes(ax, lat_mid)
    fig.canvas.draw()

    def offset_line(a, b, off_pt):
        """把航段在显示坐标中沿法向平移 off_pt 点，用于并排显示不同机型。"""
        pa = ax.transData.transform(a)
        pb = ax.transData.transform(b)
        d = pb - pa
        nrm = np.array([-d[1], d[0]]) / np.hypot(*d)
        shift = nrm * off_pt * fig.dpi / 72
        inv = ax.transData.inverted()
        return inv.transform(pa + shift), inv.transform(pb + shift)

    o = (nodes["O01"]["lon"], nodes["O01"]["lat"])
    by_site = defaultdict(list)
    for (s, g), n in pair_count.items():
        by_site[s].append((g, n))
    for s, lst in sorted(by_site.items()):
        lst.sort()
        k = len(lst)
        for i, (g, n) in enumerate(lst):
            off = (i - (k - 1) / 2) * 2.4
            pa, pb = offset_line(o, (nodes[s]["lon"], nodes[s]["lat"]), off)
            ax.plot([pa[0], pb[0]], [pa[1], pb[1]], color=fk.C[g], lw=0.7 + 0.55 * n, alpha=0.9,
                    solid_capstyle="round", zorder=2)
    # 多点路线：同一有向航段同机型合并计数；各段沿飞行方向左侧平移，反向重合的航段因此分开
    directed = defaultdict(list)
    for t in multi:
        seq = ["O01"] + t["order"] + ["O01"]
        for a, b in zip(seq, seq[1:]):
            directed[(a, b, t["type"])].append(t["id"])
    for (a, b, g), ids in sorted(directed.items()):
        pa, pb = offset_line((nodes[a]["lon"], nodes[a]["lat"]), (nodes[b]["lon"], nodes[b]["lat"]), MULTI_SHIFT)
        ax.add_patch(FancyArrowPatch(tuple(pa), tuple(pb), arrowstyle="-|>", mutation_scale=8,
                                     lw=1.3 + 0.5 * len(ids), color=fk.C[g], shrinkA=4, shrinkB=6, zorder=3,
                                     linestyle=(0, (5, 1.6))))
    for t in multi:
        a, b = t["order"][0], t["order"][1]
        mid = ((nodes[a]["lon"] + nodes[b]["lon"]) / 2, (nodes[a]["lat"] + nodes[b]["lat"]) / 2)
        dx, dy = ROUTE_LABEL_OFFSET[t["id"]]
        ax.annotate(t["id"], mid, xytext=(dx, dy), textcoords="offset points", fontsize=10,
                    ha="left" if dx >= 0 else "right", va="center", color=fk.C["ink"], zorder=7,
                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.8))

    for n in nodes.values():
        if n["id"] == "O01":
            ax.scatter(n["lon"], n["lat"], marker="*", s=150, color=fk.C["ink"], edgecolor="white",
                       linewidth=0.6, zorder=5)
            ax.annotate("O01", (n["lon"], n["lat"]), xytext=(7, -11), textcoords="offset points",
                        fontsize=10, zorder=7)
        else:
            ax.scatter(n["lon"], n["lat"], marker="o", s=34, facecolor="white", edgecolor=fk.C["ink"],
                       linewidth=1.0, zorder=5)
            dx, dy = LABEL_OFFSET[n["id"]]
            ax.annotate(n["id"], (n["lon"], n["lat"]), xytext=(dx, dy), textcoords="offset points",
                        fontsize=10, ha="left" if dx >= 0 else "right", va="center", zorder=7,
                        bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.6))
    ax.set_xlabel(L["common"]["lon"])
    ax.set_ylabel(L["common"]["lat"])
    fk.north_arrow(ax)
    fk.scale_bar(ax, lat_mid, km=2)

    handles = [Line2D([], [], color=fk.C[g], lw=2.2, label=L["common"][f"type_{g}"]) for g in "ABC"]
    handles += [Line2D([], [], color=fk.C["muted"], lw=1.2, label=L["F03"]["single"]),
                Line2D([], [], color=fk.C["muted"], lw=1.7, ls=(0, (5, 1.6)), marker=">", markersize=5,
                       label=L["F03"]["multi"]),
                Line2D([], [], marker="*", ls="none", color=fk.C["ink"], markersize=9, label=L["common"]["O01"]),
                Line2D([], [], marker="o", ls="none", mfc="white", mec=fk.C["ink"], markersize=5.5,
                       label=L["common"]["site"])]
    fig.legend(handles=handles, loc="outside lower center", ncol=7, columnspacing=0.9, handletextpad=0.35,
               handlelength=1.5)

    fk.write_csv(HERE / f"{STEM}.csv", rows)
    single_n = sum(1 for t in tasks if len(t["order"]) == 1)
    counts = {g: sum(1 for t in tasks if t["type"] == g) for g in "ABC"}
    fk.save(fig, HERE, STEM, figure_id="F3",
            caption="问题二运输路线（24 个架次）",
            section="7.4.1",
            sources=[q2p, fk.NODE_XLSX, fk.DEM_TIF],
            key_values={"sorties": len(tasks), "single_point": single_n, "multi_point": len(multi),
                        "type_counts": counts,
                        "multi_routes": {t["id"]: t["type"] + ":" + "→".join(["O01"] + t["order"] + ["O01"]) for t in multi},
                        "legs_total": sum(1 for r in rows if r["record"] == "leg")},
            notes="单点往返的去程与回程共用一条连线，线宽 = 0.7 + 0.55 × 该机型在该航段的架次数；同一服务区有多种机型时并排平移 2.4 pt。多点路线用虚线箭头画出全部三段。底图为原题 30 m DEM 山体阴影（光源方位 315°、高度角 45°）。")


if __name__ == "__main__":
    main()
