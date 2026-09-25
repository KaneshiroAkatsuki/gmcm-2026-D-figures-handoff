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
    assert len(rows) >= 2 and len({r["soc"] for r in rows}) == len(rows)
    x = [float(r["soc"]) for r in rows]
    y = [float(r["charge_seconds"]) for r in rows]
    knee = next(r for r in rows if float(r["soc"]) == 0.9)
    kx, ky = float(knee["soc"]), float(knee["charge_seconds"])
    full_time = max(y)
    fig, ax = plt.subplots(figsize=(15.5 / 2.54, 3.40))
    fig.subplots_adjust(left=0.12, right=0.97, top=0.88, bottom=0.24)
    ax.plot(x, y, color="#245A81", linewidth=1.8, label="两阶段等效充电")
    ax.scatter([kx], [ky], color="#AD542B", s=27, zorder=3)
    ax.annotate(f"({kx:.1f}, {ky:.0f} s)", (kx, ky), xytext=(0.57, full_time * 0.70),
                arrowprops=dict(arrowstyle="->", color="#555555", linewidth=0.7), fontsize=10)
    ax.set_xlabel("荷电状态 SOC", fontsize=10)
    ax.set_ylabel("充满所需时间 / s", fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, full_time * 1.08)
    ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.yaxis.set_major_locator(MultipleLocator(300))
    ax.grid(color="#D4DAE1", linewidth=0.45, linestyle="--")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper right")
    fig.text(0.5, 0.062, f"两阶段等效充电曲线（示例充满时长 {full_time:.0f} s）", ha="center", fontsize=11)
    out = root / "output"
    out.mkdir(exist_ok=True)
    for suffix in ["png", "svg"]:
        fig.savefig(out / (stem + "." + suffix), dpi=300)
    plt.close(fig)
    print(stem + ": completed PNG/SVG from " + str(len(rows)) + " CSV rows.")


if __name__ == "__main__":
    main()
