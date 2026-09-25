"""F10 问题二与问题三逐箱送达对比：80 箱按服务区排列，每箱画两个方案的送达时刻，并标出期望送达时刻与硬截止。

数据：results/q2.json、results/q3.json 各架次的 deliveries（整批交接完成时刻）；原题逐箱货箱清单。
硬截止与附件 dcore.inputs 口径相同：医疗物资取期望送达时刻，首批保障箱取首批截止时刻，两者都有时取较小者。
加权平均送达以应急优先系数为权；绘图前核对 Q2 为 2931.434 s、Q3 为 3456.307 s，且两方案均无硬截止违约。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator

STEM = "fig_box_delivery"
COL = {"Q2": "#0072B2", "Q3": "#E69F00"}
MK = {"Q2": "o", "Q3": "^"}
HARD = "#B84438"
YMAX = 12600


def hard_due(b):
    due = []
    if b["category"] == "医疗物资":
        due.append(b["expected"])
    if b["first"] == "是":
        due.append(b["first_due"])
    return min(due) if due else None


def main():
    fk.setup()
    L = fk.labels()
    LF = L["F10"]
    paths = {"Q2": fk.RESULTS / "q2.json", "Q3": fk.RESULTS / "q3.json"}
    deliv = {}
    for k, p in paths.items():
        q = fk.load_json(p)
        d = {}
        for t in q["tasks"]:
            for bid, tm in t["deliveries"].items():
                assert bid not in d
                d[bid] = tm
        assert len(d) == 80
        deliv[k] = d
    boxes = fk.boxes()
    order = sorted(boxes, key=lambda i: (boxes[i]["site"], i))
    sites = sorted({b["site"] for b in boxes.values()})

    wavg, avg = {}, {}
    for k, d in deliv.items():
        wavg[k] = sum(boxes[i]["priority"] * d[i] for i in order) / sum(boxes[i]["priority"] for i in order)
        avg[k] = sum(d.values()) / len(d)
    assert round(wavg["Q2"], 3) == 2931.434 and round(wavg["Q3"], 3) == 3456.307

    fig, ax = plt.subplots(figsize=(fk.FULL_W, 8.6 * fk.CM), layout="constrained")
    rows, over = [], []
    x = 0
    centers = []
    for si, s in enumerate(sites):
        ids = [i for i in order if boxes[i]["site"] == s]
        x0 = x
        if si % 2 == 0:
            ax.axvspan(x0 - 0.5, x0 + len(ids) - 0.5, color=fk.C["light"], lw=0, zorder=0)
        for i in ids:
            b = boxes[i]
            hd = hard_due(b)
            ax.plot([x - 0.38, x + 0.38], [b["expected"]] * 2, color=fk.C["muted"], lw=1.4, zorder=2,
                    solid_capstyle="butt")
            if hd is not None:
                ax.plot([x - 0.42, x + 0.42], [hd] * 2, color=HARD, lw=1.8, zorder=3, solid_capstyle="butt")
            if b["expected"] > YMAX:
                over.append(x)
            row = {"x": x, "box": i, "site": s, "category": b["category"], "priority": b["priority"],
                   "expected_s": b["expected"], "hard_due_s": "" if hd is None else hd}
            for k in ["Q2", "Q3"]:
                row[f"{k}_delivery_s"] = deliv[k][i]
                if hd is not None:
                    assert deliv[k][i] <= hd + 1e-7
                    row[f"{k}_hard_slack_s"] = hd - deliv[k][i]
            rows.append(row)
            x += 1
        centers.append((x0 + x - 1) / 2)
    xs = [r["x"] for r in rows]
    for k, dx in [("Q2", -0.17), ("Q3", 0.17)]:
        ax.scatter([v + dx for v in xs], [r[f"{k}_delivery_s"] for r in rows], marker=MK[k], s=13,
                   color=COL[k], edgecolor="white", linewidth=0.3, zorder=5)
        ax.axhline(wavg[k], color=COL[k], lw=1.1, ls=(0, (5, 2)) if k == "Q2" else (0, (1.5, 1.2)), zorder=4)
    ax.scatter(over, [YMAX] * len(over), marker="^", s=16, color=fk.C["muted"], zorder=4, clip_on=False)
    ax.set_xlim(-0.8, len(xs) - 0.2)
    ax.set_ylim(0, YMAX)
    ax.yaxis.set_major_locator(MultipleLocator(1800))
    ax.set_xticks(centers)
    ax.set_xticklabels(sites, rotation=90)
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel(LF["ylabel"])
    ax.set_xlabel(LF["xlabel"])
    ax.grid(axis="y", zorder=1)
    ax.set_axisbelow(True)
    handles = [Line2D([], [], marker="o", ls="none", color=COL["Q2"], markersize=4.5, label=LF["q2"]),
               Line2D([], [], marker="^", ls="none", color=COL["Q3"], markersize=5, label=LF["q3"]),
               Line2D([], [], color=fk.C["muted"], lw=1.4, label=LF["expected"]),
               Line2D([], [], color=HARD, lw=1.8, label=LF["hard"]),
               Line2D([], [], color=COL["Q2"], lw=1.1, ls=(0, (5, 2)), label=f"Q2 {LF['wavg']} {wavg['Q2']:.3f} s"),
               Line2D([], [], color=COL["Q3"], lw=1.1, ls=(0, (1.5, 1.2)), label=f"Q3 {LF['wavg']} {wavg['Q3']:.3f} s"),
               Line2D([], [], marker="^", ls="none", color=fk.C["muted"], markersize=4.5, label=LF["over"].format(y=YMAX))]
    fig.legend(handles=handles, loc="outside lower center", ncol=3, columnspacing=1.1, handletextpad=0.4)
    fk.write_csv(HERE / f"{STEM}.csv", rows)
    slack = {k: min(r[f"{k}_hard_slack_s"] for r in rows if r["hard_due_s"] != "") for k in ["Q2", "Q3"]}
    fk.save(fig, HERE, STEM, figure_id="F10",
            caption="问题二与问题三逐箱送达时刻对比",
            section="8.7（配合 S1；附录表20、21 可压缩）",
            sources=[paths["Q2"], paths["Q3"], fk.BOX_XLSX],
            key_values={"weighted_mean_delivery_s": {k: round(v, 6) for k, v in wavg.items()},
                        "mean_delivery_s": {k: round(v, 6) for k, v in avg.items()},
                        "weighted_gap_Q3_minus_Q2_s": round(wavg["Q3"] - wavg["Q2"], 6),
                        "min_hard_slack_s": {k: round(v, 6) for k, v in slack.items()},
                        "boxes": len(rows), "boxes_with_hard_due": sum(1 for r in rows if r["hard_due_s"] != ""),
                        "expected_above_axis": len(over)},
            notes="送达时刻为该站整批交接完成时刻；灰色短线为期望送达时刻，红色短线为硬截止（与期望时刻相同时红线覆盖灰线）；"
                  f"期望时刻超过 {YMAX} s 的 {len(over)} 箱在纵轴顶端以灰色三角示意。加权平均以应急优先系数为权。")


if __name__ == "__main__":
    main()
