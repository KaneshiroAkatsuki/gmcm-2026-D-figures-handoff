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
    assert rows
    assert set(r["plan"] for r in rows) == {"不分区", "2组", "3组"}
    assert len({(r["plan"], r["resource"]) for r in rows}) == len(rows)
    keys = ["drone_A", "drone_B", "drone_C", "battery_A", "battery_B", "battery_C", "relay", "component"]
    labels = ["A 型\n无人机", "B 型\n无人机", "C 型\n无人机", "A 型\n电池", "B 型\n电池", "C 型\n电池", "中继\n无人机", "中继\n组件"]
    plans = ["不分区", "2组", "3组"]
    colors = ["#A1AAB3", "#2D6B91", "#B65D3B"]
    fig, ax = plt.subplots(figsize=(15.5 / 2.54, 3.75))
    fig.subplots_adjust(left=0.10, right=0.98, top=0.84, bottom=0.29)
    for index, plan in enumerate(plans):
        values = {r["resource"]: int(r["count"]) for r in rows if r["plan"] == plan}
        for x, key in enumerate(keys):
            value = values[key]
            xpos = x + (index - 1) * 0.24
            ax.bar(xpos, value, width=0.23, color=colors[index], label=plan if x == 0 else None)
            ax.text(xpos, value + 0.07, str(value), ha="center", va="bottom", fontsize=10)
    ax.set_xticks(range(8), labels, fontsize=10)
    ax.set_ylabel("资源总需求 / 件", fontsize=10)
    ax.set_ylim(0, max(int(r["count"]) for r in rows) + 1)
    ax.yaxis.set_major_locator(MultipleLocator(1))
    ax.grid(axis="y", color="#D4DAE1", linewidth=0.45, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.30))
    fig.text(0.5, 0.105, "Q4 分区资源总需求（允许复制中继，资源优先主方案）", ha="center", fontsize=11)
    fig.text(0.5, 0.046, "比较未分区基准与两组、三组总需求；资源总需求不等于库存缺口。", ha="center", fontsize=10)
    out = root / "output"
    out.mkdir(exist_ok=True)
    for suffix in ["png", "svg"]:
        fig.savefig(out / (stem + "." + suffix), dpi=300)
    plt.close(fig)
    print(stem + ": completed PNG/SVG from " + str(len(rows)) + " CSV rows.")


if __name__ == "__main__":
    main()
