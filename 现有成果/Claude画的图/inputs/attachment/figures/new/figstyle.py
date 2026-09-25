"""公共样式：中文宋体、数字 Times New Roman，仅输出 PNG(300 dpi)/SVG。"""
import sys
sys.dont_write_bytecode = True
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
COLORS = {"A": "#2D6B91", "B": "#B65D3B", "C": "#5B7842", "gray": "#8D99A4", "relay": "#8A63A8"}


def setup():
    for family in ["Times New Roman", "SimSun"]:
        font_manager.findfont(family, fallback_to_default=False)
    plt.rcParams.update({"font.family": ["Times New Roman", "SimSun"], "font.size": 10.5,
                         "axes.unicode_minus": False, "pdf.fonttype": 42, "ps.fonttype": 42,
                         "svg.fonttype": "path", "axes.linewidth": 0.6, "savefig.facecolor": "white",
                         "mathtext.fontset": "stix"})


def read(stem):
    with (HERE / f"{stem}.csv").open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save(fig, stem):
    out = HERE / "output"
    out.mkdir(exist_ok=True)
    for suffix in ["png", "svg"]:
        fig.savefig(out / f"{stem}.{suffix}", dpi=300)
    plt.close(fig)
    print(f"{stem}: PNG/SVG 已输出")


def tidy(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(length=2.5, width=0.5)
    ax.grid(color="#D4DAE1", linestyle="--", linewidth=0.45)
    ax.set_axisbelow(True)
