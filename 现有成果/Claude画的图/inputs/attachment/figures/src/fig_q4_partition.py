"""Plot selected Q4 service-area groupings from one CSV; no optimizer is invoked."""
import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
import csv
import math
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator, FormatStrFormatter


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    root = Path(__file__).resolve().parent
    with (root / "fig_q4_partition.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows and set(r["scheme"] for r in rows) == {"copy_2", "copy_3", "no_copy_3"}
    expected_nodes = {r["node"] for r in rows}
    for family in ["Times New Roman", "SimSun"]:
        font_manager.findfont(family, fallback_to_default=False)
    plt.rcParams.update({"font.family": ["Times New Roman", "SimSun"], "font.size": 10,
                         "axes.unicode_minus": False, "pdf.fonttype": 42, "ps.fonttype": 42,
                         "svg.fonttype": "path", "axes.linewidth": 0.6, "savefig.facecolor": "white"})
    groups = {"G1": ("#0072B2", "o"), "G2": ("#D55E00", "s"), "G3": ("#009E73", "^")}
    schemes = [("copy_2", "(a) 允许复制中继：两组主方案"), ("copy_3", "(b) 允许复制中继：三组主方案"), ("no_copy_3", "(c) 禁止复制中继：三组对照")]
    fig, axes = plt.subplots(3, 1, figsize=(15.5 / 2.54, 8.8), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.12, right=0.96, top=0.955, bottom=0.16, hspace=0.29)
    longitudes = [float(row["longitude"]) for row in rows]
    latitudes = [float(row["latitude"]) for row in rows]
    for ax, (scheme, title) in zip(axes, schemes):
        subset = [r for r in rows if r["scheme"] == scheme]
        assert subset and {r["node"] for r in subset} == expected_nodes
        assert len(subset) == len(expected_nodes)
        for row in subset:
            x, y = float(row["longitude"]), float(row["latitude"])
            if row["node_type"] == "center":
                ax.scatter(x, y, marker="*", s=95, color="#222222", edgecolor="white", linewidth=0.5, zorder=4)
            else:
                color, marker = groups[row["group"]]
                ax.scatter(x, y, marker=marker, s=43, facecolor=color, edgecolor="white", linewidth=0.6, zorder=3)
            offset = (4, 4)
            if row["node"] in {"S014", "S010"}:
                offset = (-5, 4)
            elif row["node"] == "S012":
                offset = (7, 3)
            ax.annotate(row["node"], (x, y), xytext=offset, textcoords="offset points",
                        ha="right" if offset[0] < 0 else "left", va="bottom", fontsize=10, color="#242F39")
        ax.set_xlim(min(longitudes) - 0.009, max(longitudes) + 0.011)
        ax.set_ylim(min(latitudes) - 0.008, max(latitudes) + 0.009)
        # Equal physical scale locally: longitude degree is scaled by cos(latitude).
        ax.set_aspect(1 / math.cos(math.radians(sum(latitudes) / len(latitudes))))
        ax.set_title(title, loc="left", fontsize=10, pad=7)
        ax.set_ylabel("纬度 / °N", fontsize=10)
        ax.xaxis.set_major_locator(MultipleLocator(0.04))
        ax.yaxis.set_major_locator(MultipleLocator(0.02))
        ax.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
        ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
        ax.grid(color="#D4DAE1", linestyle="--", linewidth=0.45)
        ax.set_axisbelow(True)
        ax.tick_params(length=2.5, width=0.5, labelsize=10)
        ax.spines[["top", "right"]].set_visible(False)
    axes[-1].set_xlabel("经度 / °E", fontsize=10, labelpad=5)
    handles = [Line2D([], [], linestyle="none", marker=marker, markerfacecolor=color, markeredgecolor="white", markersize=7, label=group) for group, (color, marker) in groups.items()]
    handles.append(Line2D([], [], linestyle="none", marker="*", color="#222222", markersize=9, label="调度中心 O01"))
    fig.legend(handles=handles, ncol=4, loc="lower center", bbox_to_anchor=(0.53, 0.079), frameon=False, fontsize=10, handletextpad=0.2, columnspacing=1.5)
    fig.text(0.5, 0.047, "Q4 服务区任务分区：主方案与禁止复制对照", ha="center", fontsize=11)
    fig.text(0.5, 0.025, "颜色与形状表示所属组；组号按面板独立定义。", ha="center", fontsize=10)
    out = root / "output"
    out.mkdir(exist_ok=True)
    for suffix in ["png", "svg"]:
        fig.savefig(out / f"fig_q4_partition.{suffix}", dpi=300)
    plt.close(fig)
    print(f"Q4 partition figure completed: {len(schemes)} selected schemes, {len(expected_nodes)} nodes per panel.")


if __name__ == "__main__":
    main()
