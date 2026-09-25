"""图13 改进版：问题二运输实体的任务占用及返航时刻（原图源 figures/src/fig_q2_timeline.py 的副本修改）。

改动：删去图内标题与注释（“编号省略 Q2-；色带为准备至返航，未计电池充电”移入图题）；字体与输出沿用本文件夹公共样式。
数据：原图源同名 CSV（各任务的机型、实体、开始与返航时刻），原样复制到本文件夹。
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

STEM = "fig_q2_timeline"
SRC_CSV = fk.ORIG_FIG / "src" / f"{STEM}.csv"


def main():
    fk.setup()
    L = fk.labels()
    rows = fk.read_source_csv(SRC_CSV)
    assert rows and len({r["task"] for r in rows}) == len(rows) == 24
    entities = sorted({r["entity"] for r in rows})
    colors = {"A": "#2D6B91", "B": "#B65D3B", "C": "#5B7842"}
    fig, ax = plt.subplots(figsize=(fk.FULL_W, 7.4 * fk.CM), layout="constrained")
    for row in rows:
        start, end = float(row["start"]), float(row["end"])
        y = entities.index(row["entity"])
        ax.barh(y, end - start, left=start, height=0.63, color=colors[row["kind"]], edgecolor="white", linewidth=0.5)
        ax.text((start + end) / 2, y, row["task"].removeprefix("Q2-"), ha="center", va="center", color="white", fontsize=10)
    ax.set_yticks(range(len(entities)), entities)
    ax.set_ylim(len(entities) - 0.5, -0.5)
    ax.set_xlim(0, math.ceil(max(float(r["end"]) for r in rows) / 2000) * 2000)
    ax.set_xlabel(L["common"]["time_s"])
    ax.set_ylabel("运输无人机")
    ax.xaxis.set_major_locator(MultipleLocator(2000))
    ax.grid(axis="x", zorder=0)
    ax.set_axisbelow(True)
    fig.legend(handles=[Patch(facecolor=c, label=f"{k} 型") for k, c in colors.items()], ncol=3,
               loc="outside upper center")
    fk.copy_source_csv(SRC_CSV, HERE, STEM)
    fk.save(fig, HERE, STEM, figure_id="图13（改进版）",
            caption="问题二运输实体的任务占用及返航时刻（编号省略“Q2-”；色带为准备开始至返航，不含电池充电）",
            section="7.5", sources=[SRC_CSV],
            key_values={"tasks": len(rows), "entities": entities,
                        "makespan_s": max(float(r["end"]) for r in rows)},
            notes="与原图相比只删去图内标题和注释，数据与画法不变。")


if __name__ == "__main__":
    main()
