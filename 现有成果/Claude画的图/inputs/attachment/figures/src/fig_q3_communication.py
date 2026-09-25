"""Plot selected nominal communication intervals and relay service windows from one CSV."""
import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator
from matplotlib import font_manager


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    root = Path(__file__).resolve().parent
    with (root / "fig_q3_communication.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    states = [r for r in rows if r["record_type"] == "interval"]
    windows = [r for r in rows if r["record_type"] == "service_window"]
    task_ids = sorted({r["task"] for r in states})
    assert states and task_ids and windows
    relay_ids = sorted({row["relay"] for row in windows})
    assert len(relay_ids) == len(windows)
    for family in ["Times New Roman", "SimSun"]:
        font_manager.findfont(family, fallback_to_default=False)
    plt.rcParams.update({"font.family": ["Times New Roman", "SimSun"], "font.size": 10,
                         "axes.unicode_minus": False, "pdf.fonttype": 42, "ps.fonttype": 42,
                         "svg.fonttype": "path", "axes.linewidth": 0.6, "savefig.facecolor": "white"})
    palette = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#332288", "#999933"]
    colors = {"direct": "#8D99A4", **{relay: palette[index % len(palette)] for index, relay in enumerate(relay_ids)}}
    fig, (ax, ar) = plt.subplots(2, 1, figsize=(15.5 / 2.54, 8.55), sharex=True,
                                 gridspec_kw={"height_ratios": [len(task_ids), len(windows)], "hspace": 0.22})
    fig.subplots_adjust(left=0.17, right=0.97, top=0.89, bottom=0.145)
    ymap = {task: index for index, task in enumerate(task_ids)}
    for row in states:
        start, end = float(row["start"]), float(row["end"])
        key = "direct" if row["mode"] == "direct" else row["relay"]
        assert end > start and key in colors
        ax.barh(ymap[row["task"]], end - start, left=start, height=0.72,
                color=colors[key], edgecolor="none", linewidth=0)
        # Preserve every source interval; subtle boundaries remain visible when enlarged.
        ax.plot([start, start], [ymap[row["task"]] - 0.36, ymap[row["task"]] + 0.36],
                color="white", linewidth=0.12, alpha=0.7)
    ax.set_yticks(range(len(task_ids)), task_ids, fontsize=10)
    ax.set_ylim(len(task_ids) - 0.2, -0.8)
    ax.set_title(f"运输架次：{len(task_ids)} 个；标称实际状态段：{len(states)} 个", loc="left", fontsize=10, pad=7)
    for index, row in enumerate(sorted(windows, key=lambda r: r["relay"])):
        start, end = float(row["start"]), float(row["end"])
        ar.barh(index, end - start, left=start, height=0.60, color=colors[row["relay"]], edgecolor="#3D4852", linewidth=0.5)
        ar.plot([start, end], [index, index], "|", color="#253441", markersize=7, markeredgewidth=0.8)
    ar.set_yticks(range(len(windows)), [r["relay"] for r in sorted(windows, key=lambda r: r["relay"])], fontsize=10)
    ar.set_ylim(len(windows) - 0.2, -0.8)
    ar.set_title("中继服务窗", loc="left", fontsize=10, pad=6)
    ar.set_xlabel("时间 / s", fontsize=10, labelpad=5)
    max_time = max(float(row["end"]) for row in rows)
    ar.set_xlim(0, (int(max_time / 1000) + 1) * 1000)
    ar.xaxis.set_major_locator(MultipleLocator(1000))
    for axis in [ax, ar]:
        axis.grid(axis="x", color="#CDD4DC", linestyle="--", linewidth=0.45, zorder=0)
        axis.set_axisbelow(True)
        axis.tick_params(axis="both", length=2.5, width=0.5)
        axis.spines[["top", "right"]].set_visible(False)
    handles = [Patch(facecolor=colors["direct"], label="直连")]
    handles.extend(Patch(facecolor=colors[relay], label="中继 " + relay) for relay in relay_ids)
    fig.legend(handles=handles, ncol=4, loc="upper center", bbox_to_anchor=(0.53, 0.972), frameon=False,
               fontsize=10, columnspacing=1.0, handlelength=1.25, handletextpad=0.45)
    fig.text(0.5, 0.056, "Q3 通信保障：标称实际状态与中继服务窗", ha="center", fontsize=11)
    fig.text(0.5, 0.031, "色带为开区间状态；切换瞬时另按区间与边界证书判定。", ha="center", fontsize=10)
    out = root / "output"
    out.mkdir(exist_ok=True)
    for suffix in ["png", "svg"]:
        fig.savefig(out / f"fig_q3_communication.{suffix}", dpi=300)
    plt.close(fig)
    print(f"Q3 communication figure completed: {len(states)} intervals, {len(task_ids)} transports, {len(windows)} service windows.")


if __name__ == "__main__":
    main()
