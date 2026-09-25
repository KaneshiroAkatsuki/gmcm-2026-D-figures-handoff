"""图20 改进版：问题三各运输架次的标称实际通信状态（原图源 figures/src/fig_q3_communication.py 的副本修改）。

改动：按架次开始时刻排序；图幅按原尺寸插入即可保证字号不小于 10 pt；删去与图19 重复的“中继服务窗”子图；
删去图内标题与注释（移入图题）。数据仍取原图源同名 CSV 的 interval 记录，全部 525 个状态段逐段画出。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

STEM = "fig_q3_communication"
SRC_CSV = fk.ORIG_FIG / "src" / f"{STEM}.csv"
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#332288", "#999933"]


def main():
    fk.setup()
    L = fk.labels()
    rows = fk.read_source_csv(SRC_CSV)
    states = [r for r in rows if r["record_type"] == "interval"]
    windows = [r for r in rows if r["record_type"] == "service_window"]
    relay_ids = sorted({r["relay"] for r in windows})
    assert len(states) == 525 and len(relay_ids) == 6
    colors = {"direct": "#8D99A4", **{rid: PALETTE[i % len(PALETTE)] for i, rid in enumerate(relay_ids)}}
    first = {}
    for r in states:
        first[r["task"]] = min(first.get(r["task"], 1e18), float(r["start"]))
    task_ids = sorted(first, key=lambda t: (first[t], t))
    assert len(task_ids) == 25

    fig, ax = plt.subplots(figsize=(fk.FULL_W, 11.6 * fk.CM), layout="constrained")
    ymap = {t: i for i, t in enumerate(task_ids)}
    for r in states:
        a, b = float(r["start"]), float(r["end"])
        key = "direct" if r["mode"] == "direct" else r["relay"]
        assert b > a and key in colors
        ax.barh(ymap[r["task"]], b - a, left=a, height=0.74, color=colors[key], edgecolor="none", linewidth=0)
    ax.set_yticks(range(len(task_ids)), task_ids)
    ax.set_ylim(len(task_ids) - 0.4, -0.6)
    tmax = max(float(r["end"]) for r in states)
    ax.set_xlim(0, (int(tmax / 1000) + 1) * 1000)
    ax.xaxis.set_major_locator(MultipleLocator(1000))
    ax.set_xlabel(L["common"]["time_s"])
    ax.grid(axis="x", zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    handles = [Patch(fc=colors["direct"], label="直连")] + [Patch(fc=colors[r], label="中继 " + r) for r in relay_ids]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, columnspacing=1.2, handletextpad=0.35,
               handlelength=1.2)
    fk.copy_source_csv(SRC_CSV, HERE, STEM)
    n_relay = sum(1 for r in states if r["mode"] != "direct")
    fk.save(fig, HERE, STEM, figure_id="图20（改进版）",
            caption="问题三各运输架次的实际通信状态（按开始时刻排列）",
            section="8.6.3",
            sources=[SRC_CSV],
            key_values={"transports": len(task_ids), "state_intervals": len(states), "direct_intervals": len(states) - n_relay,
                        "relay_intervals": n_relay, "order": task_ids},
            notes="色带为标称实际状态的开区间段，切换瞬时另按区间与边界证书判定（写入图题）。中继服务窗见图19，本图不再重复。")


if __name__ == "__main__":
    main()
