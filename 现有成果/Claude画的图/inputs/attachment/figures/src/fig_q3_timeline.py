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
    transports = [r for r in rows if r["kind"] in ["A", "B", "C"]]
    relay_rows = [r for r in rows if r["kind"] not in ["A", "B", "C"]]
    entities = sorted({r["entity"] for r in transports}) + sorted({r["entity"] for r in relay_rows})
    colors = {"A": "#2D6B91", "B": "#B65D3B", "C": "#5B7842", "准备/航行/建链": "#B6BCC5", "通信保障窗": "#8660A8", "返航后周转": "#E3E6EB"}
    fig, ax = plt.subplots(figsize=(15.5 / 2.54, 4.55))
    fig.subplots_adjust(left=0.105, right=0.945, top=0.84, bottom=0.24)
    for row in rows:
        start, end = float(row["start"]), float(row["end"])
        y = entities.index(row["entity"])
        ax.barh(y, end - start, left=start, height=0.64, color=colors[row["kind"]],
                edgecolor="#84909B" if row["kind"] == "返航后周转" else "white", linewidth=0.35, hatch="///" if row["kind"] == "返航后周转" else None)
        if row["kind"] in ["A", "B", "C"]:
            ax.text((start + end) / 2, y, row["task"].removeprefix("Q3-"), ha="center", va="center", color="white", fontsize=10)
        elif row["kind"] == "通信保障窗":
            ax.text((start + end) / 2, y, row["task"], ha="center", va="center", color="white", fontsize=10)
    ax.set_yticks(range(len(entities)), entities)
    ax.set_ylim(len(entities) - 0.5, -0.5)
    ax.set_xlim(0, math.ceil(max(float(r["end"]) for r in rows) / 2000) * 2000)
    ax.set_xlabel("时间 / s", fontsize=10)
    ax.set_ylabel("无人机实体", fontsize=10)
    ax.xaxis.set_major_locator(MultipleLocator(2000))
    ax.axhline(len(set(r["entity"] for r in transports)) - 0.5, color="#657382", linewidth=0.6)
    ax.grid(axis="x", color="#D4DAE1", linewidth=0.45, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    handles = [Patch(facecolor=colors[k], label=f"{k} 型运输") for k in ["A", "B", "C"]]
    handles += [Patch(facecolor=colors["准备/航行/建链"], label="中继任务跨度"), Patch(facecolor=colors["通信保障窗"], label="中继服务窗"), Patch(facecolor=colors["返航后周转"], hatch="///", label="中继返航后周转")]
    fig.legend(handles=handles, ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.53, 0.995), fontsize=10, columnspacing=1.2)
    fig.text(0.5, 0.1, "Q3 运输实体与中继服务时间线", ha="center", fontsize=11)
    fig.text(0.5, 0.052, "运输编号省略 Q3-；中继服务窗叠加于任务跨度。", ha="center", fontsize=10)
    out = root / "output"
    out.mkdir(exist_ok=True)
    for suffix in ["png", "svg"]:
        fig.savefig(out / (stem + "." + suffix), dpi=300)
    plt.close(fig)
    print(stem + ": completed PNG/SVG from " + str(len(rows)) + " CSV rows.")


if __name__ == "__main__":
    main()
