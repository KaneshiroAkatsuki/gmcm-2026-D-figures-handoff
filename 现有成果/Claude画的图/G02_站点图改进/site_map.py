"""图2 改进版：起降点与服务区需求的空间分布（原图源 figures/fusion/site_map.py 的副本修改）。

改动：加原题 30 m DEM 山体阴影底图（30 m 栅格的等高线过碎，未采用）；气泡面积仍与服务区物资总质量成正比，另给气泡尺寸图例；
删去图内说明文字（移入图题与图例）；按与其他地图一致的等比例经纬度坐标、比例尺与指北针。
数据：原图源所用 data/site_demand.csv（原样复制为本图同名 CSV）；原题 DEM。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import numpy as np
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

STEM = "site_map"
SRC_CSV = fk.ATTACH / "data" / "site_demand.csv"
SIZE_K = 2.6          # 与原图相同：气泡面积 = 2.6 × 总质量（pt²）
LABEL_OFFSET = {"S001": (7, -6), "S002": (7, 5), "S003": (-8, 7), "S004": (7, 6), "S005": (-8, 7),
                "S006": (-7, -11), "S007": (-7, -11), "S008": (7, 6), "S009": (7, 5), "S010": (8, -9),
                "S011": (-8, 7), "S012": (7, 5), "S013": (7, 6), "S014": (7, -11), "S015": (-8, 7)}


def main():
    fk.setup()
    L = fk.labels()
    rows = fk.read_source_csv(SRC_CSV)
    sites = [r for r in rows if r["节点"] != "O01"]
    o = next(r for r in rows if r["节点"] == "O01")
    nodes = fk.nodes()
    for r in rows:
        assert abs(float(r["经度"]) - nodes[r["节点"]]["lon"]) < 1e-9 and abs(float(r["纬度"]) - nodes[r["节点"]]["lat"]) < 1e-9
    lons = [float(r["经度"]) for r in rows]
    lats = [float(r["纬度"]) for r in rows]
    lat_mid = (min(lats) + max(lats)) / 2
    x0, x1 = min(lons) - 0.010, max(lons) + 0.012
    y0, y1 = min(lats) - 0.008, max(lats) + 0.009
    dem = fk.DEM()
    sub, extent, _ = dem.window(x0, x1, y0, y1)
    hs = dem.hillshade(sub, lat_mid)
    fig, ax = plt.subplots(figsize=(fk.FULL_W, 11.2 * fk.CM), layout="constrained")
    ax.imshow(0.60 + 0.40 * hs, extent=extent, cmap="gray", vmin=0, vmax=1, interpolation="bilinear", zorder=0)
    for r in sites:
        x, y, m = float(r["经度"]), float(r["纬度"]), float(r["总质量_kg"])
        ax.scatter(x, y, s=m * SIZE_K, facecolor="#E9F0F3", edgecolor=fk.C["direct"], linewidth=1.2, alpha=0.9, zorder=3)
        dx, dy = LABEL_OFFSET[r["节点"]]
        ax.annotate(r["节点"], (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=10, zorder=4,
                    ha="left" if dx >= 0 else "right", va="center",
                    bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.7))
    ax.scatter(float(o["经度"]), float(o["纬度"]), marker="*", s=175, color="#B84438", edgecolor="white", linewidth=0.6, zorder=5)
    ax.annotate("O01 起降点", (float(o["经度"]), float(o["纬度"])), xytext=(8, -11), textcoords="offset points", fontsize=10,
                zorder=5, bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.75))
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    fk.map_axes(ax, lat_mid)
    ax.set_xlabel(L["common"]["lon"])
    ax.set_ylabel(L["common"]["lat"])
    fk.north_arrow(ax)
    fk.scale_bar(ax, lat_mid, km=2)
    handles = [Line2D([], [], marker="o", ls="none", mfc="#E9F0F3", mec=fk.C["direct"], mew=1.2,
                      markersize=np.sqrt(m * SIZE_K), label=f"{m} kg") for m in (50, 100, 150)]
    handles += [Line2D([], [], marker="*", ls="none", color="#B84438", markersize=11, label="起降点 O01"),
]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, columnspacing=1.8, handletextpad=1.0, handlelength=2.4,
               title="气泡面积对应服务区物资总质量", title_fontsize=10)
    fk.copy_source_csv(SRC_CSV, HERE, STEM)
    fk.save(fig, HERE, STEM, figure_id="图2（改进版）",
            caption="起降点与服务区需求的空间分布（底图为 DEM 山体阴影；气泡面积对应物资总质量）",
            section="5.1.1", sources=[SRC_CSV, fk.DEM_TIF, fk.NODE_XLSX],
            key_values={"service_sites": len(sites), "mass_total_kg": sum(float(r["总质量_kg"]) for r in sites)},
            notes="气泡面积与质量成线性关系（与原图相同）；底图为原题 30 m DEM 山体阴影（光源方位 315°、高度角 45°）。")


if __name__ == "__main__":
    main()
