"""F2 连续通信证明原理示意图（两类闭区间证书，均取问题三的真实区间）。

(a)(b)(c) 扫掠三角形净空证书：Q3-H1-2 巡航段 2914.418–2947.430 s，由中继 R-004 保障。
    中继点 𝔅 与运动段 𝔄₀𝔄₁ 构成的三角形投影到 DEM 像元格网；逐像元裁剪后，视线高度是平面上的
    仿射函数，其最小值只可能出现在三类候选点：三角形顶点、三角形内的像元格角、三角形边与像元边界的交点。
    (c) 为经过最小净空点的视线剖面。
(d) 距离凸性证书：全局最小裕量所在的 Q3-006 下降段 2771.260–2856.230 s（R-004 保障），
    按全程遮挡计损耗，由端点最大距离给出整段裕量下界。
数值全部由附件正式函数（src/dcore.py、src/bounded_certificates.py）按 results/q3.json 的区间端点重算，
并与 q3.json 中的证书逐项核对。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "lib"))
import math
import numpy as np
import figkit as fk
sys.path.insert(0, str(fk.SRC))
from dcore import inputs, Terrain, budget, loss, guaranteed_radius
from bounded_certificates import minimum_clearance, point_on
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon, Rectangle, Patch
from matplotlib.ticker import MultipleLocator

STEM = "fig_comm_proof"
TRI = dict(task="Q3-H1-2", event=2, relay="R-004", start=2914.4180303205717)
DIST = dict(task="Q3-006", event=3, relay="R-004", start=2771.2601412514014)
ZOOM = dict(c0=746, c1=764, r0=587, r1=601)     # 放大窗口（像元列、行范围）
KEY = 1e-9


def plane(P):
    """由三个 (列, 行, 高度) 顶点求 z = a·列 + b·行 + c。"""
    M = np.array([[p[0], p[1], 1.0] for p in P])
    return np.linalg.solve(M, np.array([p[2] for p in P]))


def clip(poly, axis, value, sense):
    out = []
    prev = poly[-1]
    dp = sense * (prev[axis] - value)
    for cur in poly:
        dc = sense * (cur[axis] - value)
        if (dp >= -1e-12) != (dc >= -1e-12):
            t = dp / (dp - dc)
            x = [prev[k] + t * (cur[k] - prev[k]) for k in range(2)]
            x[axis] = value
            out.append(tuple(x))
        if dc >= -1e-12:
            out.append(tuple(cur))
        prev, dp = cur, dc
    return out


def classify(pt, verts):
    for v in verts:
        if abs(pt[0] - v[0]) < KEY and abs(pt[1] - v[1]) < KEY:
            return "vertex"
    on_c = abs(pt[0] - round(pt[0])) < KEY
    on_r = abs(pt[1] - round(pt[1])) < KEY
    return "corner" if (on_c and on_r) else "edge"


def main():
    fk.setup()
    L = fk.labels()
    q3p = fk.RESULTS / "q3.json"
    q3 = fk.load_json(q3p)
    nodes, types, drones, boxes, relay, comm = inputs()
    T = Terrain(nodes)
    rel = {r["id"]: r for r in q3["relays"]}
    tasks = {t["id"]: t for t in q3["tasks"]}
    ivs = q3["communication"]["intervals"]

    def interval(spec):
        return [i for i in ivs if i["task"] == spec["task"] and i["event"] == spec["event"]
                and i["relay"] == spec["relay"] and abs(i["start"] - spec["start"]) < 1e-9][0]

    def xyz(p):
        return np.array([*T.xy(p[0], p[1]), p[2]], dtype=float)

    lim = budget(comm, "T", "A")

    # ---------- 扫掠三角形证书 ----------
    it = interval(TRI)
    ev = tasks[TRI["task"]]["events"][TRI["event"]]
    p0, p1 = point_on(ev, it["start"]), point_on(ev, it["end"])
    Bpos = rel[TRI["relay"]]["position"]
    clr, cell = minimum_clearance(T, Bpos, p0, p1)
    dmax = max(float(np.linalg.norm(xyz(p) - xyz(Bpos))) for p in [p0, p1])
    m_clear, m_block = lim - loss(comm, dmax, False), lim - loss(comm, dmax, True)
    cert = it["certificate"]
    assert cert["method"] == "closed_swept_triangle_clearance"
    assert clr == cert["clearance_lower_m"] and cell == cert["critical_cell"] and m_clear == cert["margin_lower_db"]
    assert m_block < 0.01

    Bg, A0g, A1g = [np.array([*T.grid(p[0], p[1]), p[2]]) for p in (Bpos, p0, p1)]
    verts = [tuple(Bg[:2]), tuple(A0g[:2]), tuple(A1g[:2])]
    coef = plane([Bg, A0g, A1g])
    zfun = lambda c, r: coef[0] * c + coef[1] * r + coef[2]

    # 放大窗口内逐像元裁剪，收集三类候选点
    pts, cells_hit, best = {}, [], (math.inf, None, None)
    for r in range(ZOOM["r0"], ZOOM["r1"]):
        for c in range(ZOOM["c0"], ZOOM["c1"]):
            poly = [tuple(v) for v in verts]
            for axis, value, sense in [(0, c, 1), (0, c + 1, -1), (1, r, 1), (1, r + 1, -1)]:
                poly = clip(poly, axis, value, sense) if poly else []
            if not poly:
                continue
            h = float(T.a[r, c])
            cells_hit.append((r, c))
            for p in poly:
                key = (round(p[0], 7), round(p[1], 7))
                pts.setdefault(key, (p, classify(p, verts)))
                g = zfun(*p) - h
                if g < best[0]:
                    best = (g, (r, c), p)
    assert abs(best[0] - clr) < 1e-6 and list(best[1]) == cell, (best, clr, cell)
    crit_r, crit_c = cell
    crit_h = float(T.a[crit_r, crit_c])
    pstar = best[2]

    # 经过最小净空点的视线：pstar = B + u(A* − B)
    d = np.array(pstar) - Bg[:2]
    M = np.column_stack([A0g[:2] - Bg[:2], A1g[:2] - A0g[:2]])
    u, v = np.linalg.solve(M, d)
    frac = v / u
    tstar = it["start"] + frac * (it["end"] - it["start"])
    Astar = point_on(ev, tstar)
    cells = T.cells((Bpos[0], Bpos[1]), (Astar[0], Astar[1]))
    hlen = float(np.linalg.norm(xyz(Astar)[:2] - xyz(Bpos)[:2]))
    los = lambda s: Bpos[2] + (Astar[2] - Bpos[2]) * s
    prof_clear = min(min(los(lo), los(hi)) - z for _, _, lo, hi, z in cells)
    assert abs(prof_clear - clr) < 1e-6

    # ---------- 距离凸性证书 ----------
    idd = interval(DIST)
    ev2 = tasks[DIST["task"]]["events"][DIST["event"]]
    B2 = rel[DIST["relay"]]["position"]
    ts = np.linspace(idd["start"], idd["end"], 121)
    D = np.array([np.linalg.norm(xyz(point_on(ev2, t)) - xyz(B2)) for t in ts])
    marg = np.array([lim - loss(comm, x, True) for x in D])
    dend = max(D[0], D[-1])
    bound = lim - loss(comm, dend, True)
    assert idd["certificate"]["method"] == "closed_distance_convexity_full_obstruction"
    assert bound == idd["certificate"]["margin_lower_db"] == q3["communication"]["min_certified_margin_db"]
    Robs = guaranteed_radius(comm, "T", "A")

    # ---------- 绘图 ----------
    fig = plt.figure(figsize=(fk.FULL_W, 12.4 * fk.CM), layout="constrained")
    fig.get_layout_engine().set(wspace=0.06, hspace=0.04)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.0], height_ratios=[1.45, 1.0])
    axA, axB = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])
    sub = gs[1, :].subgridspec(1, 2, width_ratios=[1.65, 1.0])
    axC, axD = fig.add_subplot(sub[0]), fig.add_subplot(sub[1])

    km = lambda p: xyz(p)[:2] / 1000.0
    kx, ky = T.kx, T.ky
    tri_km = np.array([km(Bpos), km(p0), km(p1)])
    o = km((nodes["O01"]["lon"], nodes["O01"]["lat"], 0))
    s7 = km((nodes["S007"]["lon"], nodes["S007"]["lat"], 0))
    xs = [tri_km[:, 0].min(), tri_km[:, 0].max(), o[0], s7[0]]
    ys = [tri_km[:, 1].min(), tri_km[:, 1].max(), o[1], s7[1]]
    x0, x1, y0, y1 = min(xs) - 0.45, max(xs) + 0.55, min(ys) - 0.45, max(ys) + 0.45
    lon0, lat0 = T.lonlat(x0 * 1000, y0 * 1000)
    lon1, lat1 = T.lonlat(x1 * 1000, y1 * 1000)
    dem = fk.DEM()
    win, ext, _ = dem.window(lon0, lon1, lat0, lat1)
    hs = dem.hillshade(win, nodes["O01"]["lat"])
    e0 = km((ext[0], ext[2], 0))
    e1 = km((ext[1], ext[3], 0))
    axA.imshow(0.62 + 0.38 * hs, extent=(e0[0], e1[0], e0[1], e1[1]), cmap="gray", vmin=0, vmax=1,
               interpolation="bilinear", origin="upper", zorder=0)
    axA.plot([o[0], s7[0]], [o[1], s7[1]], color=fk.C["A"], lw=1.0, ls=(0, (3, 2)), zorder=2)
    axA.add_patch(Polygon(tri_km, closed=True, fc=fk.C["relay"], alpha=0.28, ec=fk.C["relay"], lw=1.0, zorder=3))
    axA.annotate("", xy=tri_km[2], xytext=tri_km[1],
                 arrowprops=dict(arrowstyle="-|>", color=fk.C["A"], lw=1.6, mutation_scale=9), zorder=4)
    axA.scatter(tri_km[:, 0], tri_km[:, 1], marker="^", s=30, color=fk.C["ink"], zorder=5)
    S = fk.labels()["sym"]
    axA.annotate(f"{S['relay_pt']}（R-004）", tri_km[0], xytext=(-4, 7), textcoords="offset points",
                 ha="right", fontsize=10, zorder=6)
    axA.annotate(S["A0"], tri_km[1], xytext=(4, -11), textcoords="offset points", fontsize=10, zorder=6)
    axA.annotate(S["A1"], tri_km[2], xytext=(-4, 6), textcoords="offset points", ha="right", fontsize=10, zorder=6)
    axA.scatter([o[0]], [o[1]], marker="*", s=90, color=fk.C["ink"], zorder=5)
    axA.annotate("O01", o, xytext=(5, -3), textcoords="offset points", fontsize=10, va="top")
    mid = (o + s7) / 2
    axA.annotate("Q3-H1-2 航线", mid, xytext=(10, 6), textcoords="offset points", fontsize=10,
                 color=fk.C["A"], rotation=0)
    zx0, zy0 = km((dem.left + ZOOM["c0"] * dem.dx, dem.top - ZOOM["r1"] * dem.dy, 0))
    zx1, zy1 = km((dem.left + ZOOM["c1"] * dem.dx, dem.top - ZOOM["r0"] * dem.dy, 0))
    axA.add_patch(Rectangle((zx0, zy0), zx1 - zx0, zy1 - zy0, fc="none", ec=fk.C["inventory"], lw=1.0, zorder=6))
    axA.annotate("(b)", (zx1, zy1), xytext=(3, 2), textcoords="offset points", fontsize=10,
                 color=fk.C["inventory"])
    axA.set_xlim(x0, x1)
    axA.set_ylim(y0, y1)
    axA.set_aspect("equal")
    axA.set_xlabel(L["F02"]["east"])
    axA.set_ylabel(L["F02"]["north"])
    axA.xaxis.set_major_locator(MultipleLocator(1))
    axA.yaxis.set_major_locator(MultipleLocator(1))

    # (b) 放大：像元边界、三角形、三类候选点（坐标以 𝔅 的水平位置为原点，单位 m）
    def to_m(c, r):
        lon = dem.left + c * dem.dx
        lat = dem.top - r * dem.dy
        return np.array([(lon - Bpos[0]) * kx, (lat - Bpos[1]) * ky])
    for c in range(ZOOM["c0"], ZOOM["c1"] + 1):
        a, b = to_m(c, ZOOM["r0"]), to_m(c, ZOOM["r1"])
        axB.plot([a[0], b[0]], [a[1], b[1]], color="#C3CAD0", lw=0.5, zorder=1)
    for r in range(ZOOM["r0"], ZOOM["r1"] + 1):
        a, b = to_m(ZOOM["c0"], r), to_m(ZOOM["c1"], r)
        axB.plot([a[0], b[0]], [a[1], b[1]], color="#C3CAD0", lw=0.5, zorder=1)
    cc0, cc1 = to_m(crit_c, crit_r + 1), to_m(crit_c + 1, crit_r)
    axB.add_patch(Rectangle(tuple(cc0), cc1[0] - cc0[0], cc1[1] - cc0[1], fc="#F3D3CF", ec=fk.C["inventory"],
                            lw=1.0, zorder=1.5))
    tri_m = np.array([to_m(*vv) for vv in verts])
    axB.add_patch(Polygon(tri_m, closed=True, fc=fk.C["relay"], alpha=0.22, ec=fk.C["relay"], lw=0.9, zorder=2))
    style = {"vertex": dict(marker="^", s=46, color=fk.C["ink"], zorder=6),
             "corner": dict(marker="o", s=16, color=fk.C["A"], zorder=5),
             "edge": dict(marker="o", s=14, facecolor="white", edgecolor=fk.C["relay"], linewidths=0.8, zorder=5)}
    count = {"vertex": 0, "corner": 0, "edge": 0}
    cand_rows = []
    for (p, kind) in pts.values():
        q = to_m(*p)
        if ZOOM["c0"] <= p[0] <= ZOOM["c1"] and ZOOM["r0"] <= p[1] <= ZOOM["r1"]:
            axB.scatter([q[0]], [q[1]], **style[kind])
            count[kind] += 1
            cand_rows.append({"panel": "b", "kind": kind, "col": p[0], "row": p[1], "east_m": q[0], "north_m": q[1],
                              "los_height_m": zfun(*p)})
    ps = to_m(*pstar)
    axB.scatter([ps[0]], [ps[1]], marker="*", s=90, color=fk.C["inventory"], zorder=7)
    axB.annotate(f"最小净空 {clr:.3f} m\n像元 [{crit_r}, {crit_c}]，高程 {crit_h:.3f} m",
                 ps, xytext=(0.03, 0.97), textcoords="axes fraction", fontsize=10, ha="left", va="top",
                 arrowprops=dict(arrowstyle="->", lw=0.7, color=fk.C["inventory"]),
                 bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9), zorder=8)
    axB.annotate(S["relay_pt"], tri_m[0], xytext=(5, 4), textcoords="offset points", fontsize=10, zorder=8)
    lo_m, hi_m = to_m(ZOOM["c0"], ZOOM["r1"]), to_m(ZOOM["c1"], ZOOM["r0"])
    axB.set_xlim(lo_m[0], hi_m[0])
    axB.set_ylim(lo_m[1], hi_m[1])
    axB.set_aspect("equal")
    axB.set_xlabel(L["F02"]["east_m"])
    axB.set_ylabel(L["F02"]["north_m"])
    axB.xaxis.set_major_locator(MultipleLocator(100))
    axB.yaxis.set_major_locator(MultipleLocator(100))
    for s in ["top", "right"]:
        axB.spines[s].set_visible(True)

    # (c) 视线剖面
    prof_rows = []
    for (r, c, lo, hi, z) in cells:
        prof_rows.append({"panel": "c", "kind": "dem_cell", "col": c, "row": r, "s_from_km": lo * hlen / 1000,
                          "s_to_km": hi * hlen / 1000, "height_m": z})
    grid_s = np.linspace(0, 1, 6001)
    zmax = np.full_like(grid_s, np.nan)
    for (r, c, lo, hi, z) in cells:
        m = (grid_s >= lo) & (grid_s <= hi)
        zmax[m] = np.fmax(zmax[m], z)
    axC.fill_between(grid_s * hlen / 1000, 0, zmax, color="#D5DADE", lw=0, zorder=1)
    axC.plot(grid_s * hlen / 1000, zmax, color=fk.C["muted"], lw=0.8, zorder=2)
    sx = np.array([0, 1.0])
    axC.plot(sx * hlen / 1000, [los(0), los(1)], color=fk.C["relay"], lw=1.5, zorder=3)
    su = u * hlen / 1000
    axC.annotate(f"最小净空 {clr:.3f} m", (su, los(u)), xytext=(su + 0.9, 300), fontsize=10,
                 arrowprops=dict(arrowstyle="->", lw=0.7, color=fk.C["inventory"]), color=fk.C["inventory"])
    axC.scatter([su], [los(u)], marker="*", s=70, color=fk.C["inventory"], zorder=5)
    axC.annotate(S["relay_pt"], (0, los(0)), xytext=(4, 5), textcoords="offset points", fontsize=10)
    axC.annotate(f"{S['A0']}{S['A1']} 上的点", (hlen / 1000, los(1)), xytext=(-4, 5), textcoords="offset points",
                 fontsize=10, ha="right", va="bottom")
    axC.set_xlim(0, hlen / 1000)
    axC.set_ylim(100, 580)
    axC.yaxis.set_major_locator(MultipleLocator(200))
    axC.set_xlabel(L["F02"]["dist"])
    axC.set_ylabel(L["F02"]["height"])
    axC.grid(axis="y")
    axC.set_axisbelow(True)
    # (d) 距离凸性：实际裕量与由端点距离得到的整段下界
    tt = ts - ts[0]
    axD.plot(tt, marg, color=fk.C["relay"], lw=1.5, zorder=3)
    axD.axhline(bound, color=fk.C["ink"], lw=1.0, ls=(0, (4, 2)), zorder=2)
    axD.axhline(0.01, color=fk.C["inventory"], lw=1.0, ls=(0, (1.5, 1.5)), zorder=2)
    axD.text(2, bound + 0.0012, f"整段下界 {bound:.6f}", ha="left", va="bottom", fontsize=10)
    axD.text(2, 0.0088, "稳健门槛 0.01", ha="left", va="top", fontsize=10, color=fk.C["inventory"])
    axD.set_xlim(0, tt[-1])
    axD.set_ylim(0.0, 0.045)
    axD.set_xlabel(f"下降段内时间/s")
    axD.set_ylabel("计遮挡裕量/dB")
    axD.yaxis.set_major_locator(MultipleLocator(0.01))
    axD.grid(axis="y")
    axD.set_axisbelow(True)

    for ax, lab in zip([axA, axB, axC, axD], "abcd"):
        fk.panel_label(ax, f"({lab})", x=-0.02, y=1.01)

    handles = [Patch(fc=fk.C["relay"], alpha=0.28, ec=fk.C["relay"], label=L["F02"]["triangle"]),
               Line2D([], [], marker="^", ls="none", color=fk.C["ink"], markersize=6, label=L["F02"]["cand_vertex"]),
               Line2D([], [], marker="o", ls="none", color=fk.C["A"], markersize=4.5, label=L["F02"]["cand_corner"]),
               Line2D([], [], marker="o", ls="none", mfc="white", mec=fk.C["relay"], markersize=4.5,
                      label=L["F02"]["cand_edge"]),
               Patch(fc="#F3D3CF", ec=fk.C["inventory"], label=L["F02"]["critical"]),
               Line2D([], [], color=fk.C["relay"], lw=1.5, label=L["F02"]["los"]),
               Patch(fc="#D5DADE", ec=fk.C["muted"], lw=0.8, label=L["F02"]["dem"])]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, columnspacing=0.9, handletextpad=0.4)

    rows = cand_rows + prof_rows
    for t, x, mg in zip(ts, D, marg):
        rows.append({"panel": "d", "kind": "distance_margin", "time_s": t, "distance_m": x, "margin_db": mg})
    fk.write_csv(HERE / f"{STEM}.csv", rows,
                 ["panel", "kind", "col", "row", "east_m", "north_m", "los_height_m", "s_from_km", "s_to_km",
                  "height_m", "time_s", "distance_m", "margin_db"])
    fk.save(fig, HERE, STEM, figure_id="F2",
            caption="连续通信的两类闭区间证书",
            section="8.5.2",
            sources=[q3p, fk.SRC / "dcore.py", fk.SRC / "bounded_certificates.py", fk.DEM_TIF, fk.NODE_XLSX,
                     fk.COMM_XLSX],
            key_values={
                "triangle_interval": {"task": TRI["task"], "event": TRI["event"], "relay": TRI["relay"],
                                      "start_s": it["start"], "end_s": it["end"],
                                      "margin_clear_db": m_clear, "margin_if_blocked_db": m_block,
                                      "max_distance_m": dmax, "min_clearance_m": clr, "critical_cell": cell,
                                      "critical_cell_height_m": crit_h, "critical_time_s": tstar,
                                      "candidate_counts_in_zoom": count, "cells_in_zoom_hit": len(cells_hit)},
                "distance_interval": {"task": DIST["task"], "event": DIST["event"], "relay": DIST["relay"],
                                      "start_s": idd["start"], "end_s": idd["end"],
                                      "distance_start_m": float(D[0]), "distance_end_m": float(D[-1]),
                                      "margin_start_db": float(marg[0]), "margin_lower_db": bound,
                                      "obstructed_radius_m": Robs},
                "global_min_certified_margin_db": q3["communication"]["min_certified_margin_db"]},
            notes="(a) 坐标为以 O01 为原点的局部平面（km）；(b) 以 𝔅 的水平位置为原点（m），灰线为 DEM 像元边界；"
                  "(c) 横轴为沿视线的水平距离，折线为视线穿过的像元高程；(d) 横轴自下降段开始计时。"
                  "候选点只画 (b) 窗口内的部分；全区间的最小净空由附件 minimum_clearance 计算并与 q3.json 核对。")


if __name__ == "__main__":
    main()
