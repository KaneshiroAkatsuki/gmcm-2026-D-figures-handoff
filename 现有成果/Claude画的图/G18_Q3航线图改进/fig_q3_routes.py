"""图18 改进版：问题三运输航线、通信保障方式与中继悬停点（原图源 figures/src/fig_q3_routes.py 的副本修改）。

改动：加原题 DEM 山体阴影底图；巡航航段按标称实际通信状态分段着色（直连或经中继）；画出各中继悬停点到 G01 的
回传链路；拉开 P4、P5 的标签；删去图内标题与说明（移入图题）。
数据：原图源同名 CSV（节点、中继点位、51 条航段，原样复制）；分段着色取 results/q3.json 中 nominal_communication 的
巡航事件区间（按区间的参数起止在航段上线性插值）。同一航段被多架次或往返重复使用时，先画直连段再在其上叠画中继段，
因此橙色表示该位置至少有一次经中继保障。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
from collections import Counter
from fractions import Fraction
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

STEM = "fig_q3_routes"
SRC_CSV = fk.ORIG_FIG / "src" / f"{STEM}.csv"
COL_DIRECT = "#3D697A"
COL_RELAY = "#CB8E3C"
LABEL_OFFSET = {"S001": (7, -6), "S002": (7, 5), "S003": (-8, 7), "S004": (7, 6), "S005": (-8, 7),
                "S006": (-7, -11), "S007": (-7, -11), "S008": (7, 6), "S009": (7, 5), "S010": (-8, -9),
                "S011": (-8, 7), "S012": (7, 5), "S013": (7, 6), "S014": (7, -11), "S015": (-8, 7),
                "P1": (-8, 8), "P2": (7, 7), "P3": (7, 7), "P4": (-12, 14), "P5": (12, -14)}


def main():
    fk.setup()
    L = fk.labels()
    rows = fk.read_source_csv(SRC_CSV)
    nodes = [r for r in rows if r["record_type"] == "node"]
    relay_pts = [r for r in rows if r["record_type"] == "relay_location"]
    legs = [r for r in rows if r["record_type"] == "leg"]
    assert len(legs) == 51 and len(relay_pts) == 5
    pts = {r["node"]: (float(r["longitude"]), float(r["latitude"])) for r in nodes + relay_pts}
    q3p = fk.RESULTS / "q3.json"
    q3 = fk.load_json(q3p)
    tasks = {t["id"]: t for t in q3["tasks"]}
    assert Counter(r["task"] for r in legs) == Counter({t: len(tasks[t]["order"]) + 1 for t in tasks})
    for r in q3["relays"]:
        assert any(abs(r["position"][0] - p[0]) < 1e-12 and abs(r["position"][1] - p[1]) < 1e-12 for p in pts.values())

    # 巡航事件的标称状态分段
    segs = {"direct": [], "relay": []}
    out_rows = []
    for iv in q3["nominal_communication"]["intervals"]:
        e = tasks[iv["task"]]["events"][iv["event"]]
        assert e["phase"] == iv["phase"]
        if e["phase"] != "巡航":
            continue
        a, b = float(Fraction(iv["parameter_start"])), float(Fraction(iv["parameter_end"]))
        p0, p1 = e["p0"], e["p1"]
        xa, ya = p0[0] + (p1[0] - p0[0]) * a, p0[1] + (p1[1] - p0[1]) * a
        xb, yb = p0[0] + (p1[0] - p0[0]) * b, p0[1] + (p1[1] - p0[1]) * b
        kind = "direct" if iv["mode"] == "direct" else "relay"
        segs[kind].append(((xa, xb), (ya, yb)))
        out_rows.append({"record_type": "cruise_state", "task": iv["task"], "event": iv["event"], "mode": kind,
                         "relay": iv["relay"], "param_start": a, "param_end": b, "lon0": xa, "lat0": ya, "lon1": xb, "lat1": yb})

    lons = [p[0] for p in pts.values()]
    lats = [p[1] for p in pts.values()]
    lat_mid = (min(lats) + max(lats)) / 2
    x0, x1 = min(lons) - 0.010, max(lons) + 0.012
    y0, y1 = min(lats) - 0.008, max(lats) + 0.009
    dem = fk.DEM()
    sub, extent, _ = dem.window(x0, x1, y0, y1)
    hs = dem.hillshade(sub, lat_mid)
    fig, ax = plt.subplots(figsize=(fk.FULL_W, 11.4 * fk.CM), layout="constrained")
    ax.imshow(0.62 + 0.38 * hs, extent=extent, cmap="gray", vmin=0, vmax=1, interpolation="bilinear", zorder=0)
    pair = Counter(tuple(sorted([r["from_node"], r["to_node"]])) for r in legs)
    for kind, col, z in [("direct", COL_DIRECT, 2), ("relay", COL_RELAY, 3)]:
        for xs, ys in segs[kind]:
            ax.plot(xs, ys, color=col, lw=1.8, solid_capstyle="butt", zorder=z)
    g = pts["O01"]
    for r in relay_pts:
        ax.plot(*zip(g, pts[r["node"]]), color=fk.C["relay"], lw=0.9, ls=(0, (1.5, 1.5)), zorder=2.5)
    for name, (x, y) in pts.items():
        if name.startswith("P"):
            ax.scatter(x, y, marker="^", s=62, color=fk.C["relay"], edgecolor="white", linewidth=0.55, zorder=5)
        elif name == "O01":
            ax.scatter(x, y, marker="*", s=150, color=fk.C["ink"], edgecolor="white", linewidth=0.6, zorder=5)
            ax.annotate("O01 / G01", (x, y), xytext=(8, -11), textcoords="offset points", fontsize=10, zorder=6,
                        bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.75))
            continue
        else:
            ax.scatter(x, y, marker="o", s=34, facecolor="white", edgecolor=fk.C["ink"], linewidth=1.0, zorder=5)
        dx, dy = LABEL_OFFSET[name]
        lead = dict(arrowstyle="-", color=fk.C["muted"], lw=0.5, shrinkA=0, shrinkB=3) if name in ("P4", "P5") else None
        ax.annotate(name, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=10, zorder=6,
                    ha="left" if dx >= 0 else "right", va="center", arrowprops=lead,
                    color=fk.C["relay"] if name.startswith("P") else fk.C["ink"],
                    bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.75))
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    fk.map_axes(ax, lat_mid)
    ax.set_xlabel(L["common"]["lon"])
    ax.set_ylabel(L["common"]["lat"])
    fk.north_arrow(ax)
    fk.scale_bar(ax, lat_mid, km=2)
    handles = [Line2D([], [], color=COL_DIRECT, lw=1.8, label="巡航段：直连"),
               Line2D([], [], color=COL_RELAY, lw=1.8, label="巡航段：经中继"),
               Line2D([], [], marker="^", color=fk.C["relay"], lw=0.9, ls=(0, (1.5, 1.5)), markersize=6, mec="white",
                      label="中继悬停点与回传链路"),
               Line2D([], [], marker="o", ls="none", mfc="white", mec=fk.C["ink"], markersize=5.5, label="服务区"),
               Line2D([], [], marker="*", ls="none", color=fk.C["ink"], markersize=9, label="调度中心 O01")]
    fig.legend(handles=handles, loc="outside lower center", ncol=3, columnspacing=1.2, handletextpad=0.4)
    fk.copy_source_csv(SRC_CSV, HERE, STEM)
    fk.write_csv(HERE / f"{STEM}_通信分段.csv", out_rows)
    fk.save(fig, HERE, STEM, figure_id="图18（改进版）",
            caption="问题三运输航线、巡航段通信保障方式与中继悬停点（底图为 DEM 山体阴影）",
            section="8.6.2", sources=[SRC_CSV, q3p, fk.DEM_TIF],
            key_values={"legs": len(legs), "distinct_leg_pairs": len(pair), "relay_points": len(relay_pts),
                        "cruise_state_segments": {k: len(v) for k, v in segs.items()}},
            notes="同一航段被多个架次或往返重复使用时，橙色表示该位置至少一次经中继保障。另附 fig_q3_routes_通信分段.csv 记录全部巡航状态段。")


if __name__ == "__main__":
    main()
