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
    assert rows and len({r["task"] for r in rows}) == len(rows)
    entities = sorted({r["entity"] for r in rows})
    colors = {"A": "#2D6B91", "B": "#B65D3B", "C": "#5B7842"}
    fig, ax = plt.subplots(figsize=(15.5 / 2.54, 3.65))
    fig.subplots_adjust(left=0.11, right=0.97, top=0.86, bottom=0.25)
    for row in rows:
        start, end = float(row["start"]), float(row["end"])
        y = entities.index(row["entity"])
        ax.barh(y, end - start, left=start, height=0.63, color=colors[row["kind"]], edgecolor="white", linewidth=0.5)
        ax.text((start + end) / 2, y, row["task"].removeprefix("Q2-"), ha="center", va="center", color="white", fontsize=10)
    ax.set_yticks(range(len(entities)), entities)
    ax.set_ylim(len(entities) - 0.5, -0.5)
    ax.set_xlim(0, math.ceil(max(float(r["end"]) for r in rows) / 2000) * 2000)
    ax.set_xlabel("时间 / s", fontsize=10)
    ax.set_ylabel("运输无人机", fontsize=10)
    ax.xaxis.set_major_locator(MultipleLocator(2000))
    ax.grid(axis="x", color="#D4DAE1", linewidth=0.45, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.legend(handles=[Patch(facecolor=c, label=f"{k} 型") for k, c in colors.items()], ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.54, 0.995))
    fig.text(0.5, 0.095, "Q2 运输实体时间线", ha="center", fontsize=11)
    fig.text(0.5, 0.04, "编号省略 Q2-；色带为准备至返航，未计电池充电。", ha="center", fontsize=10)
    out = root / "output"
    out.mkdir(exist_ok=True)
    for suffix in ["png", "svg"]:
        fig.savefig(out / (stem + "." + suffix), dpi=300)
    plt.close(fig)
    print(stem + ": completed PNG/SVG from " + str(len(rows)) + " CSV rows.")


if __name__ == "__main__":
    main()
