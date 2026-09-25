"""F6 直连遮挡与中继布设地图（示意）。

底图为原题 30 m DEM 山体阴影。覆盖层：在 DEM 上每 3×3 个像元取中心像元，假设运输机位于该像元地面以上 30 m，
判断其能否与 G01（O01 处，地面以上 20 m）直连：双向门限取附件 dcore.budget(T, G) = 122 dB，
自由空间损耗按三维距离计算，视线被地形遮挡时加 10 dB（附件 dcore.loss）；遮挡判定调用附件
dcore.Terrain.los（逐像元比较视线最低高度与像元高程）。由此得到三类区域：通视且在 12.511 km 内可直连；
遮挡但在 3.956 km 内仍可直连；不可直连。两个距离圈为附件口径的两个可用半径。
叠加 5 个中继悬停点（results/q3.json 的中继任务位置，点位编号取附件 data/q3_relays.csv）及其到 G01 的回传连线、15 个服务区。
本图只是固定高度假设下的示意，不代替连续通信证明。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import csv
import math
import numpy as np
import figkit as fk
sys.path.insert(0, str(fk.SRC))
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch

STEM = "fig_direct_link_map"
STEP = 3
AGL = 30.0
COL_NEAR = "#56B4E9"
COL_NO = "#E69F00"
LABEL_OFFSET = {"S001": (6, -5), "S002": (6, 4), "S003": (-8, 6), "S004": (6, 5), "S005": (-8, 6),
                "S006": (-6, -12), "S007": (-6, -12), "S008": (6, 5), "S009": (6, 4), "S010": (8, -8),
                "S011": (-8, 6), "S012": (6, 4), "S013": (6, 5), "S014": (6, -12), "S015": (-8, 6)}
P_OFFSET = {"P1": (-7, 7), "P2": (7, 6), "P3": (7, 6), "P4": (-7, 8), "P5": (7, -9)}


def main():
    fk.setup()
    L = fk.labels()
    LF = L["F06"]
    from dcore import inputs, Terrain, budget, loss, guaranteed_radius
    nodes_d, _, _, _, _, comm = inputs()
    T = Terrain(nodes_d)
    o = nodes_d["O01"]
    gate = (o["lon"], o["lat"], o["z"] + comm["gateway_height"])
    B = budget(comm, "T", "G")
    r_block = guaranteed_radius(comm, "T", "G")
    r_clear = 1000 * 10 ** ((B - 32.45 - 20 * math.log10(comm["f"])) / 20)
    assert B == 122 and round(r_clear / 1000, 3) == 12.511 and round(r_block / 1000, 3) == 3.956

    q3p = fk.RESULTS / "q3.json"
    q3 = fk.load_json(q3p)
    relays = {r["id"]: r for r in q3["relays"]}
    relay_csv = fk.ATTACH / "data" / "q3_relays.csv"
    with relay_csv.open(encoding="utf-8-sig", newline="") as f:
        pmap = {r["中继架次"]: f"P{r['点位']}" for r in csv.DictReader(f)}
    points = {}
    for rid, r in relays.items():
        p = pmap[rid]
        if p in points:
            assert np.allclose(points[p]["pos"], r["position"])
            points[p]["ids"].append(rid)
        else:
            points[p] = {"pos": r["position"], "ids": [rid]}
    assert len(points) == 5
    nodes = fk.nodes()
    sites = sorted(k for k in nodes if k != "O01")

    lons = [nodes[s]["lon"] for s in nodes] + [p["pos"][0] for p in points.values()]
    lats = [nodes[s]["lat"] for s in nodes] + [p["pos"][1] for p in points.values()]
    lat_mid = (min(lats) + max(lats)) / 2
    x0, x1 = min(lons) - 0.012, max(lons) + 0.012
    y0, y1 = min(lats) - 0.009, max(lats) + 0.009

    # 覆盖层网格：块起点对齐到 STEP 的整数倍
    c0 = (int((x0 - T.left) / T.dx) // STEP) * STEP
    c1 = int((x1 - T.left) / T.dx) + 1
    r0 = (int((T.top - y1) / T.dy) // STEP) * STEP
    r1 = int((T.top - y0) / T.dy) + 1
    nr, nc = (r1 - r0 + STEP - 1) // STEP, (c1 - c0 + STEP - 1) // STEP
    cls = np.zeros((nr, nc), dtype=int)
    rows = []
    for i in range(nr):
        for j in range(nc):
            r, c = r0 + i * STEP + STEP // 2, c0 + j * STEP + STEP // 2
            lon, lat = T.left + (c + 0.5) * T.dx, T.top - (r + 0.5) * T.dy
            z = float(T.a[r, c]) + AGL
            p = (lon, lat, z)
            d = float(np.linalg.norm(np.r_[T.xy(lon, lat) - T.xy(gate[0], gate[1]), z - gate[2]]))
            if d > r_clear:
                k, clear = 2, ""
            else:
                clear = T.los(gate, p)
                k = 0 if clear else (1 if loss(comm, d, True) <= B else 2)
            cls[i, j] = k
            rows.append({"row": r, "col": c, "lon": lon, "lat": lat, "z_body_m": z, "dist3d_m": d,
                         "line_of_sight": clear, "class": k})
    ext = (T.left + c0 * T.dx, T.left + (c0 + nc * STEP) * T.dx, T.top - (r0 + nr * STEP) * T.dy, T.top - r0 * T.dy)

    dem = fk.DEM()
    sub, extent, _ = dem.window(x0, x1, y0, y1)
    hs = dem.hillshade(sub, lat_mid)
    fig, ax = plt.subplots(figsize=(fk.FULL_W, 11.8 * fk.CM), layout="constrained")
    ax.imshow(0.55 + 0.45 * hs, extent=extent, cmap="gray", vmin=0, vmax=1, interpolation="bilinear", zorder=0)
    over = np.ma.masked_equal(cls, 0)
    ax.imshow(over, extent=ext, cmap=ListedColormap([COL_NEAR, COL_NO]), vmin=1, vmax=2, alpha=0.38,
              interpolation="nearest", zorder=1)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    fk.map_axes(ax, lat_mid)
    kx, ky = fk.local_scale(lat_mid)
    for rad, ls in [(r_clear, (0, (6, 2.5))), (r_block, "-")]:
        th = np.linspace(0, 2 * np.pi, 361)
        ax.plot(gate[0] + rad * np.cos(th) / kx, gate[1] + rad * np.sin(th) / ky, color=fk.C["ink"], lw=1.0, ls=ls,
                zorder=3)
    ax.annotate(f"{r_block / 1000:.3f} km", (gate[0] + r_block * math.cos(math.radians(-60)) / kx,
                                             gate[1] + r_block * math.sin(math.radians(-60)) / ky),
                xytext=(4, -2), textcoords="offset points", fontsize=10, ha="left", va="top", zorder=7,
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))
    for p, v in sorted(points.items()):
        lo, la = v["pos"][:2]
        ax.plot([gate[0], lo], [gate[1], la], color=fk.C["relay"], lw=1.3, zorder=4)
        ax.scatter(lo, la, marker="^", s=60, color=fk.C["relay"], edgecolor="white", linewidth=0.6, zorder=6)
        dx, dy = P_OFFSET[p]
        ax.annotate(p, (lo, la), xytext=(dx, dy), textcoords="offset points", fontsize=10, color=fk.C["relay"],
                    ha="left" if dx >= 0 else "right", va="center", zorder=7,
                    bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.75))
    for s in sites:
        n = nodes[s]
        ax.scatter(n["lon"], n["lat"], marker="o", s=30, facecolor="white", edgecolor=fk.C["ink"], linewidth=1.0,
                   zorder=6)
        dx, dy = LABEL_OFFSET[s]
        ax.annotate(s, (n["lon"], n["lat"]), xytext=(dx, dy), textcoords="offset points", fontsize=10,
                    ha="left" if dx >= 0 else "right", va="center", zorder=7,
                    bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.7))
    ax.scatter(gate[0], gate[1], marker="*", s=150, color=fk.C["ink"], edgecolor="white", linewidth=0.6, zorder=6)
    ax.annotate("O01 / G01", (gate[0], gate[1]), xytext=(7, -11), textcoords="offset points", fontsize=10, zorder=7,
                bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.75))
    ax.set_xlabel(L["common"]["lon"])
    ax.set_ylabel(L["common"]["lat"])
    fk.north_arrow(ax)
    fk.scale_bar(ax, lat_mid, km=2)
    handles = [Patch(fc="white", ec=fk.C["muted"], lw=0.6, label=LF["clear"]),
               Patch(fc=COL_NEAR, alpha=0.38, label=LF["near"]),
               Patch(fc=COL_NO, alpha=0.38, label=LF["none"]),
               Line2D([], [], color=fk.C["ink"], lw=1.0, ls=(0, (6, 2.5)), label=f"{r_clear / 1000:.3f} km{'' if y1 - gate[1] > r_clear / ky else LF['outside']}"),
               Line2D([], [], color=fk.C["ink"], lw=1.0, label=f"{r_block / 1000:.3f} km"),
               Line2D([], [], marker="^", color=fk.C["relay"], lw=1.3, markersize=6, mec="white", label=LF["relay"]),
               Line2D([], [], marker="o", ls="none", mfc="white", mec=fk.C["ink"], markersize=5.5, label=L["common"]["site"])]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, columnspacing=1.0, handletextpad=0.4)
    fk.write_csv(HERE / f"{STEM}.csv", rows)
    n_all = cls.size
    kv = {"budget_db": B, "obstruction_db": comm["obstruction"], "radius_clear_m": r_clear, "radius_blocked_m": r_block,
          "body_agl_m": AGL, "gateway_agl_m": comm["gateway_height"], "grid_step_pixels": STEP, "grid_points": int(n_all),
          "share_clear": round(float((cls == 0).mean()), 6), "share_blocked_near": round(float((cls == 1).mean()), 6),
          "share_no_direct": round(float((cls == 2).mean()), 6),
          "relay_points": {p: {"relay_tasks": v["ids"], "lon": v["pos"][0], "lat": v["pos"][1], "z": v["pos"][2]}
                           for p, v in sorted(points.items())}}
    fk.save(fig, HERE, STEM, figure_id="F6",
            caption="G01 直连可用范围与中继布设（机体离地 30 m 的示意）",
            section="5.5 或 8.4.2（也可与图2 合并）",
            sources=[q3p, relay_csv, fk.SRC / "dcore.py", fk.DEM_TIF, fk.NODE_XLSX, fk.COMM_XLSX],
            key_values=kv,
            notes="覆盖层按“机体位于地面以上 30 m”的固定高度假设计算，每 3×3 个 DEM 像元取中心像元一点；"
                  "双向门限 122 dB，遮挡加 10 dB，距离为三维距离。本图只是示意，不代替第 8.5 节的连续通信证明。"
                  "紫色连线为中继悬停点到 G01 的回传链路；P3 上先后有 R-004 与 R-006 两个中继任务。"
                  "在该高度下，3.956 km 圈外几乎全部被地形遮挡，12.511 km 圈位于图幅以外。")


if __name__ == "__main__":
    main()
