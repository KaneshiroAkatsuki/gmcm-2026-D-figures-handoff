"""Standalone drawing from the CSV with the same filename stem."""
import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
import csv
import math
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator, FormatStrFormatter


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    root = Path(__file__).resolve().parent
    stem = Path(__file__).stem
    with (root / (stem + ".csv")).open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for family in ["Times New Roman", "SimSun"]:
        font_manager.findfont(family, fallback_to_default=False)
    plt.rcParams.update({"font.family": ["Times New Roman", "SimSun"], "font.size": 10,
                         "axes.unicode_minus": False, "pdf.fonttype": 42, "ps.fonttype": 42,
                         "svg.fonttype": "path", "axes.linewidth": 0.6, "savefig.facecolor": "white"})
    nodes = [r for r in rows if r["record_type"] == "node"]
    relays = [r for r in rows if r["record_type"] == "relay_location"]
    legs = [r for r in rows if r["record_type"] == "leg"]
    assert nodes and relays and legs
    assert len({r["node"] for r in nodes}) == len(nodes)
    assert len({r["node"] for r in relays}) == len(relays)
    points = {r["node"]: (float(r["longitude"]), float(r["latitude"])) for r in nodes}
    pair_counts = Counter(tuple(sorted([r["from_node"], r["to_node"]])) for r in legs)
    fig, ax = plt.subplots(figsize=(15.5 / 2.54, 5.6))
    fig.subplots_adjust(left=0.12, right=0.97, top=0.94, bottom=0.28)
    for (start, end), count in sorted(pair_counts.items()):
        a, b = points[start], points[end]
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#789BAF", linewidth=0.65 + 0.18 * count, alpha=0.60, zorder=1)
    for row in nodes + relays:
        x, y = float(row["longitude"]), float(row["latitude"])
        if row["record_type"] == "relay_location":
            marker, color, size = "^", "#8660A8", 62
        elif row["node"] == "O01":
            marker, color, size = "*", "#222222", 115
        else:
            marker, color, size = "o", "#2D6B91", 40
        ax.scatter(x, y, s=size, marker=marker, color=color, edgecolor="white", linewidth=0.55, zorder=3)
        offset = (5, 5)
        if row["node"] in ["S012", "S014", "S010", "P1"]:
            offset = (-5, 4)
        if row["node"] in ["P3", "P4"]:
            offset = (5, -11)
        leader = None
        if row["record_type"] == "relay_location":
            nearby = [other for other in relays if other["node"] != row["node"]
                      and math.hypot(x - float(other["longitude"]), y - float(other["latitude"])) < 0.003]
            if nearby:
                other = min(nearby, key=lambda item: math.hypot(x - float(item["longitude"]), y - float(item["latitude"])))
                offset = (-10, 12) if (x, y) < (float(other["longitude"]), float(other["latitude"])) else (10, -13)
                leader = dict(arrowstyle="-", color="#655078", linewidth=0.45, shrinkA=2, shrinkB=5)
        ax.annotate(row["node"], (x, y), xytext=offset, textcoords="offset points", ha="right" if offset[0] < 0 else "left", fontsize=10, color="#222D36", zorder=4, arrowprops=leader)
    lons = [float(r["longitude"]) for r in nodes + relays]
    lats = [float(r["latitude"]) for r in nodes + relays]
    ax.set_xlim(min(lons) - 0.009, max(lons) + 0.011)
    ax.set_ylim(min(lats) - 0.007, max(lats) + 0.009)
    ax.set_aspect(1 / math.cos(math.radians(sum(lats) / len(lats))))
    ax.set_xlabel("经度 / °E", fontsize=10)
    ax.set_ylabel("纬度 / °N", fontsize=10)
    ax.xaxis.set_major_locator(MultipleLocator(0.02))
    ax.yaxis.set_major_locator(MultipleLocator(0.02))
    ax.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax.grid(color="#D4DAE1", linewidth=0.45, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    handles = [Line2D([], [], marker="o", linestyle="none", color="#2D6B91", label="服务区"), Line2D([], [], marker="*", linestyle="none", color="#222222", markersize=9, label="调度中心"), Line2D([], [], marker="^", linestyle="none", color="#8660A8", label="中继悬停点"), Line2D([], [], color="#789BAF", linewidth=1.5, label="实际运输航段")]
    fig.legend(handles=handles, ncol=4, frameon=False, loc="lower center", bbox_to_anchor=(0.54, 0.115), fontsize=10, columnspacing=0.9, handletextpad=0.35)
    fig.text(0.5, 0.074, "Q3 实际运输航线与中继悬停位置", ha="center", fontsize=11)
    fig.text(0.5, 0.031, f"共 {len(legs)} 条实际航段；重合线合并，线宽随执行次数增加。", ha="center", fontsize=10)
    out = root / "output"
    out.mkdir(exist_ok=True)
    for suffix in ["png", "svg"]:
        fig.savefig(out / (stem + "." + suffix), dpi=300)
    plt.close(fig)
    print(stem + ": completed PNG/SVG from " + str(len(rows)) + " CSV rows.")


if __name__ == "__main__":
    main()
