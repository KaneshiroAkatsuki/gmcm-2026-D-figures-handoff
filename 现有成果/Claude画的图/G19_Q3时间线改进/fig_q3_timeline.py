"""图19 改进版：问题三运输无人机与中继无人机任务时间线（原图源 figures/src/fig_q3_timeline.py 的副本修改）。

改动：删去图内标题与注释（“运输编号省略 Q3-；中继服务窗叠加于任务跨度”移入图题）；字体与输出沿用本文件夹公共样式。
数据：原图源同名 CSV，原样复制到本文件夹。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import math
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

STEM = "fig_q3_timeline"
SRC_CSV = fk.ORIG_FIG / "src" / f"{STEM}.csv"


def main():
    fk.setup()
    L = fk.labels()
    rows = fk.read_source_csv(SRC_CSV)
    transports = [r for r in rows if r["kind"] in ["A", "B", "C"]]
    relay_rows = [r for r in rows if r["kind"] not in ["A", "B", "C"]]
    assert len(transports) == 25
    entities = sorted({r["entity"] for r in transports}) + sorted({r["entity"] for r in relay_rows})
    colors = {"A": "#2D6B91", "B": "#B65D3B", "C": "#5B7842", "准备/航行/建链": "#B6BCC5", "通信保障窗": "#8660A8",
              "返航后周转": "#E3E6EB"}
    fig, ax = plt.subplots(figsize=(fk.FULL_W, 8.6 * fk.CM), layout="constrained")
    for row in rows:
        start, end = float(row["start"]), float(row["end"])
        y = entities.index(row["entity"])
        turn = row["kind"] == "返航后周转"
        ax.barh(y, end - start, left=start, height=0.64, color=colors[row["kind"]],
                edgecolor="#84909B" if turn else "white", linewidth=0.35, hatch="///" if turn else None)
        if row["kind"] in ["A", "B", "C"]:
            ax.text((start + end) / 2, y, row["task"].removeprefix("Q3-"), ha="center", va="center", color="white", fontsize=10)
        elif row["kind"] == "通信保障窗":
            ax.text((start + end) / 2, y, row["task"], ha="center", va="center", color="white", fontsize=10)
    ax.set_yticks(range(len(entities)), entities)
    ax.set_ylim(len(entities) - 0.5, -0.5)
    ax.set_xlim(0, math.ceil(max(float(r["end"]) for r in rows) / 2000) * 2000)
    ax.set_xlabel(L["common"]["time_s"])
    ax.set_ylabel("无人机实体")
    ax.xaxis.set_major_locator(MultipleLocator(2000))
    ax.axhline(len({r["entity"] for r in transports}) - 0.5, color="#657382", linewidth=0.6)
    ax.grid(axis="x", zorder=0)
    ax.set_axisbelow(True)
    handles = [Patch(facecolor=colors[k], label=f"{k} 型运输") for k in ["A", "B", "C"]]
    handles += [Patch(facecolor=colors["准备/航行/建链"], label="中继任务跨度"),
                Patch(facecolor=colors["通信保障窗"], label="中继服务窗"),
                Patch(facecolor=colors["返航后周转"], edgecolor="#84909B", hatch="///", label="中继返航后周转")]
    fig.legend(handles=handles, ncol=3, loc="outside upper center", columnspacing=1.2)
    fk.copy_source_csv(SRC_CSV, HERE, STEM)
    fk.save(fig, HERE, STEM, figure_id="图19（改进版）",
            caption="问题三运输无人机与中继无人机任务时间线（运输编号省略“Q3-”；中继服务窗叠加于任务跨度）",
            section="8.6.2", sources=[SRC_CSV],
            key_values={"transport_tasks": len(transports), "entities": entities,
                        "service_windows": sum(1 for r in rows if r["kind"] == "通信保障窗")},
            notes="与原图相比只删去图内标题和注释，数据与画法不变。")


if __name__ == "__main__":
    main()
