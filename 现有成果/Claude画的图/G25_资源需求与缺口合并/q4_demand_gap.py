"""图25 与图26 合并版：问题四各类资源的需求、库存与缺口。

由原图源 figures/src/fig_q4_resources.py（图26，需求柱）与 figures/fusion/q4_redundancy.py（图25，冗余与缺口）
合并修改：每类资源并排画不分区、2 组、3 组（资源优先主方案）的总需求柱，叠加现有库存短线；
超出库存的部分画斜线并标注缺口件数。删去图内标题与说明。
数据：results/q4.json 的 baseline_resources、inventory 与 selected（K=2、3）；并与原图源两份 CSV 逐项核对。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

STEM = "q4_demand_gap"
KEYS = ["drone_A", "drone_B", "drone_C", "battery_A", "battery_B", "battery_C", "relay", "component"]
NAMES = ["A 型\n无人机", "B 型\n无人机", "C 型\n无人机", "A 型\n电池", "B 型\n电池", "C 型\n电池", "中继\n无人机", "中继\n组件"]
PLANS = ["不分区", "2组", "3组"]
COLORS = ["#A1AAB3", "#2D6B91", "#B65D3B"]
GAP = fk.C["inventory"]


def main():
    fk.setup()
    q4p = fk.RESULTS / "q4.json"
    src26 = fk.ORIG_FIG / "src" / "fig_q4_resources.csv"
    src25 = fk.ORIG_FIG / "fusion" / "q4_redundancy.csv"
    q = fk.load_json(q4p)
    inv = q["inventory"]
    demand = {"不分区": q["baseline_resources"]}
    shortage = {}
    for s in q["selected"]:
        demand[f"{s['K']}组"] = s["total"]
        shortage[f"{s['K']}组"] = s["shortage"]
        assert all(s["shortage"][k] == max(0, s["total"][k] - inv[k]) for k in KEYS)
        assert all(s["redundancy"][k] == s["total"][k] - q["baseline_resources"][k] for k in KEYS)
    old26 = {(r["plan"], r["resource"]): int(r["count"]) for r in fk.read_source_csv(src26)}
    assert all(old26[(p, k)] == demand[p][k] for p in PLANS for k in KEYS)
    old25 = fk.read_source_csv(src25)
    for r in old25:
        assert int(r["现有库存"]) == inv[KEYS[["A型机", "B型机", "C型机", "A型电池", "B型电池", "C型电池", "中继机", "中继组件"].index(r["资源"])]]

    fig, ax = plt.subplots(figsize=(fk.FULL_W, 7.6 * fk.CM), layout="constrained")
    rows = []
    w = 0.25
    for x, k in enumerate(KEYS):
        for i, p in enumerate(PLANS):
            val = demand[p][k]
            xp = x + (i - 1) * w
            base = min(val, inv[k])
            ax.bar(xp, base, width=w * 0.94, color=COLORS[i], zorder=3)
            gap = val - inv[k] if val > inv[k] else 0
            if gap:
                ax.bar(xp, gap, bottom=inv[k], width=w * 0.94, facecolor="white", edgecolor=GAP, hatch="////",
                       linewidth=0.8, zorder=3)
                ax.text(xp, val + 0.08, f"+{gap}", ha="center", va="bottom", fontsize=10, color=GAP, zorder=5)
            else:
                ax.text(xp, val + 0.08, str(val), ha="center", va="bottom", fontsize=10, zorder=5)
            rows.append({"resource": k, "plan": p, "demand": val, "inventory": inv[k], "shortage": gap,
                         "redundancy_vs_no_partition": val - demand["不分区"][k]})
        ax.plot([x - 1.5 * w, x + 1.5 * w], [inv[k]] * 2, color=GAP, lw=1.4, ls=(0, (5, 1.5)), zorder=4)
    ax.set_xticks(range(len(KEYS)), NAMES)
    ax.set_ylabel("资源数量/件")
    ax.set_ylim(0, max(max(d.values()) for d in demand.values()) + 1.2)
    ax.yaxis.set_major_locator(MultipleLocator(1))
    ax.grid(axis="y", zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", length=0)
    handles = [Patch(fc=c, label=f"{p}需求" if p != "不分区" else "不分区用量") for p, c in zip(PLANS, COLORS)]
    handles += [Line2D([], [], color=GAP, lw=1.4, ls=(0, (5, 1.5)), label="现有库存"),
                Patch(fc="white", ec=GAP, hatch="////", label="超出库存（缺口）")]
    fig.legend(handles=handles, loc="outside upper center", ncol=5, columnspacing=1.0, handletextpad=0.4)
    fk.write_csv(HERE / f"{STEM}.csv", rows)
    fk.save(fig, HERE, STEM, figure_id="图25+图26（合并版）",
            caption="问题四各类资源的需求、库存与缺口（资源优先主方案，跨组中继整任务复制）",
            section="9.4.2（原图25位置；原图26删除）", sources=[q4p, src26, src25],
            key_values={"inventory": inv, "demand": demand, "shortage_total": {p: sum(v.values()) for p, v in shortage.items()},
                        "shortage": shortage},
            notes="柱高为总需求；斜线部分为超出库存的缺口，柱顶“+n”为缺口件数。中继组件库存为 6，3 组方案需求 5，"
                  "有 1 件冗余但无缺口；B 型机与 B 型电池在 2 组方案中各缺 1 件，3 组方案中 B 型机缺 2、B 型电池缺 1、中继机缺 1。")


if __name__ == "__main__":
    main()
