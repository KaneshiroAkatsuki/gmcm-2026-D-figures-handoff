"""图24 改进版：问题四的分区方案（原图源 figures/src/fig_q4_partition.py 的副本修改）。

改动：由 3×1 小图改为 2×2 布局（第四格放图例与各方案缺口），放大地图；用凸包底色区分各组；
各子图组色按组成员统一（含 S001 的主组为蓝色，S011 所在组为橙色，第三组为绿色），组号仍按原结果标注；
标出不可拆单元 {S001, S005}（同一架次 Q3-M002）以及跨组复制的中继任务（悬停点处标注）；删去图内标题与说明。
数据：原图源同名 CSV（各方案各节点的组别与经纬度），并与 results/q4.json、q4_no_copy_sensitivity.json 的
selected 方案逐项核对；中继悬停点取 results/q3.json。
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
from matplotlib.patches import Patch, Polygon
from scipy.spatial import ConvexHull

STEM = "fig_q4_partition"
SRC_CSV = fk.ORIG_FIG / "src" / f"{STEM}.csv"
SCHEMES = [("copy_2", "q4", 2, "(a) 允许复制中继：两组"), ("copy_3", "q4", 3, "(b) 允许复制中继：三组"),
           ("no_copy_3", "nc", 3, "(c) 禁止复制中继：三组")]
COL = {"main": "#0072B2", "s011": "#E69F00", "third": "#009E73"}
LABEL_OFFSET = {"S001": (6, -5), "S002": (6, 4), "S003": (-7, 6), "S004": (6, 5), "S005": (-7, 6),
                "S006": (-6, -10), "S007": (-6, -10), "S008": (6, 5), "S009": (6, 5), "S010": (-7, -7),
                "S011": (-7, 6), "S012": (6, 5), "S013": (6, 5), "S014": (6, -9), "S015": (-7, 6)}


def hull_patch(pts, pad, kx, ky, **kw):
    ang = np.linspace(0, 2 * np.pi, 48, endpoint=False)
    cloud = np.array([(x + pad * math.cos(a) / kx, y + pad * math.sin(a) / ky) for x, y in pts for a in ang])
    h = ConvexHull(cloud)
    return Polygon(cloud[h.vertices], closed=True, **kw)


def role(sites):
    if "S001" in sites:
        return "main"
    if "S011" in sites:
        return "s011"
    return "third"


def main():
    fk.setup()
    rows = fk.read_source_csv(SRC_CSV)
    p4, p4n, p3 = fk.RESULTS / "q4.json", fk.RESULTS / "q4_no_copy_sensitivity.json", fk.RESULTS / "q3.json"
    res = {"q4": fk.load_json(p4), "nc": fk.load_json(p4n)}
    q3 = fk.load_json(p3)
    relays = {r["id"]: r for r in q3["relays"]}
    xy = {r["node"]: (float(r["longitude"]), float(r["latitude"])) for r in rows}
    sites = sorted(n for n in xy if n != "O01")
    lons = [p[0] for p in xy.values()] + [r["position"][0] for r in relays.values()]
    lats = [p[1] for p in xy.values()] + [r["position"][1] for r in relays.values()]
    lat_mid = (min(lats) + max(lats)) / 2
    kx, ky = fk.local_scale(lat_mid)
    x0, x1 = min(lons) - 0.010, max(lons) + 0.011
    y0, y1 = min(lats) - 0.008, max(lats) + 0.008

    fig, axs = plt.subplots(2, 2, figsize=(fk.FULL_W, 12.4 * fk.CM), layout="constrained")
    axes = [axs[0, 0], axs[0, 1], axs[1, 0]]
    info = []
    out_rows = []
    for ax, (scheme, src, K, title) in zip(axes, SCHEMES):
        sel = next(s for s in res[src]["selected"] if s["K"] == K)
        groups = {g["id"]: g for g in sel["groups"]}
        csv_groups = defaultdict(list)
        for r in rows:
            if r["scheme"] == scheme and r["group"]:
                csv_groups[r["group"]].append(r["node"])
        assert {k: sorted(v) for k, v in csv_groups.items()} == {k: sorted(g["sites"]) for k, g in groups.items()}
        relay_groups = defaultdict(list)
        for gid, g in groups.items():
            for rid in g["relay_ids"]:
                relay_groups[rid].append(gid)
        copied = {rid: gl for rid, gl in relay_groups.items() if len(gl) > 1}
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect(1 / math.cos(math.radians(lat_mid)))
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color(fk.C["grid"])
            sp.set_visible(True)
        colour = {}
        for gid, g in sorted(groups.items()):
            c = COL[role(g["sites"])]
            ax.add_patch(hull_patch([xy[s] for s in g["sites"]], 600, kx, ky, fc=c, alpha=0.16, ec=c, lw=0.9, zorder=1))
            for s in g["sites"]:
                colour[s] = c
            # 组号标注在组内最北的服务区旁
            top = max(g["sites"], key=lambda s: xy[s][1])
            if len(g["sites"]) == 1:
                ax.annotate(gid, xy[top], xytext=(0, 10 if top != "S012" else -13), textcoords="offset points",
                            ha="center", va="center", fontsize=10, color=c, fontweight="bold", zorder=7)
            else:
                ax.text(0.97, 0.96, gid, transform=ax.transAxes, ha="right", va="top", fontsize=10, color=c,
                        fontweight="bold")
            out_rows.append({"scheme": scheme, "group": gid, "colour_role": role(g["sites"]), "sites": " ".join(g["sites"]),
                             "relay_ids": " ".join(g["relay_ids"]), "shortage_total": sum(sel["shortage"].values())})
        ax.plot(*zip(xy["S001"], xy["S005"]), color=fk.C["ink"], lw=2.0, zorder=3)
        for rid, gl in sorted(copied.items()):
            lo, la = relays[rid]["position"][:2]
            ax.scatter(lo, la, marker="^", s=46, color=fk.C["relay"], edgecolor="white", linewidth=0.5, zorder=6)
            ax.annotate(rid, (lo, la), xytext=(0, -11), textcoords="offset points",
                        ha="center", va="center", fontsize=10, color=fk.C["relay"], zorder=7,
                        bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.85))
        ax.scatter(*xy["O01"], marker="*", s=100, color=fk.C["ink"], edgecolor="white", linewidth=0.5, zorder=5)
        for s in sites:
            ax.scatter(*xy[s], s=30, color=colour[s], edgecolor="white", linewidth=0.6, zorder=5)
            dx, dy = LABEL_OFFSET[s]
            ax.annotate(s, xy[s], xytext=(dx, dy), textcoords="offset points", ha="left" if dx >= 0 else "right",
                        va="center", fontsize=10, zorder=6)
        ax.text(0.0, 1.015, title, transform=ax.transAxes, ha="left", va="bottom", fontsize=10.5)
        info.append((title[:3], K, sum(sel["shortage"].values()), sel["shortage"], copied))
    fk.scale_bar(axes[0], lat_mid, km=2, x0=0.04, y0=0.88)
    # 第四格：图例与缺口
    lg = axs[1, 1]
    lg.axis("off")
    handles = [Patch(fc=COL["main"], alpha=0.35, ec=COL["main"], label="主组（含 S001）"),
               Patch(fc=COL["s011"], alpha=0.35, ec=COL["s011"], label="S011 所在组"),
               Patch(fc=COL["third"], alpha=0.35, ec=COL["third"], label="第三组"),
               Line2D([], [], color=fk.C["ink"], lw=2.0, label="单元 {S001, S005}"),
               Line2D([], [], marker="^", ls="none", color=fk.C["relay"], markersize=6, label="跨组复制的中继"),
               Line2D([], [], marker="*", ls="none", color=fk.C["ink"], markersize=9, label="O01")]
    lg.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.0), frameon=False, ncol=2, columnspacing=0.8, handletextpad=0.4)
    names = {"drone_B": "B 型机", "battery_B": "B 型电池", "relay": "中继机", "drone_A": "A 型机", "battery_A": "A 型电池",
             "drone_C": "C 型机", "battery_C": "C 型电池", "component": "中继组件"}
    lines = ["库存缺口（件）"]
    for tag, K, tot, sh, cp in info:
        items = [f"{names[k]} {v}" for k, v in sh.items() if v]
        lines.append(f"{tag} 共 {tot}：" + "、".join(items[:2]))
        if items[2:]:
            lines.append("      " + "、".join(items[2:]))
        for rid, gl in sorted(cp.items()):
            lines.append(f"      （{rid} 在 {'、'.join(gl)} 中各执行一份）")
    lg.text(0.02, 0.66, "\n".join(lines), transform=lg.transAxes, ha="left", va="top", fontsize=10, linespacing=1.5)
    fk.write_csv(HERE / f"{STEM}.csv", out_rows)
    fk.save(fig, HERE, STEM, figure_id="图24（改进版）",
            caption="问题四的分区方案：(a)(b) 跨组中继整任务复制的两组、三组主方案；(c) 禁止复制的三组对照",
            section="9.4.2", sources=[SRC_CSV, p4, p4n, p3],
            key_values={t: {"K": K, "shortage_total": tot, "copied_relays": c} for t, K, tot, _, c in info},
            notes="各子图组色按组成员统一（组号保持原结果）；凸包底色表示同组服务区；三角为在两个组中各保留一份的中继任务。")


if __name__ == "__main__":
    main()
