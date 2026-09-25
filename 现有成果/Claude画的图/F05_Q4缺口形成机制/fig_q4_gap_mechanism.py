"""F5 问题四缺口形成机制：B 型机与 B 型电池的并发数随时间变化（两组资源优先方案）。

占用区间按式(16)构造：实体 [准备开始, 返航)，电池 [准备开始, 返航 + 式(15)充电时间)，均为左闭右开；
同一时刻先释放后占用（时刻差不超过 1e-7 s 视为同刻）。分组取 results/q4.json 中 K=2 的资源优先方案。
图中峰值与 q4.json 的 baseline_resources、各组 resources 逐项核对。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import math
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

STEM = "fig_q4_gap_mechanism"
TIE = 1e-7
GCOL = {"G1": "#0072B2", "G2": "#E69F00"}


def concurrency(intervals):
    ev = sorted([(a, 1) for a, b in intervals] + [(b, -1) for a, b in intervals])
    out, c, i = [], 0, 0
    while i < len(ev):
        t0, j, d = ev[i][0], i, 0
        while j < len(ev) and ev[j][0] - t0 <= TIE:
            d += ev[j][1]
            j += 1
        c += d
        out.append((t0, c))
        i = j
    assert out[-1][1] == 0
    return out


def trim(steps):
    """去掉首尾的 0 段，只保留从首次上升到最后一次回落的部分。"""
    first = next(i for i, (_, c) in enumerate(steps) if c > 0)
    out = [(steps[first][0], 0)] + steps[first:]
    return out


def peak_windows(steps):
    pk = max(c for _, c in steps)
    wins = []
    for (t0, c), (t1, _) in zip(steps, steps[1:]):
        if c == pk:
            if wins and abs(wins[-1][1] - t0) <= TIE:
                wins[-1][1] = t1
            else:
                wins.append([t0, t1])
    return pk, wins


def main():
    fk.setup()
    L = fk.labels()
    q3p, q4p = fk.RESULTS / "q3.json", fk.RESULTS / "q4.json"
    q3, q4 = fk.load_json(q3p), fk.load_json(q4p)
    full = fk.charge_full()["B"]
    sel = [s for s in q4["selected"] if s["K"] == 2][0]
    group = {tid: g["id"] for g in sel["groups"] for tid in g["transport_ids"]}
    assert set(group.values()) == {"G1", "G2"} and [g["sites"] for g in sel["groups"] if g["id"] == "G2"][0] == ["S011"]
    tasks = [t for t in q3["tasks"] if t["type"] == "B"]
    inv = q4["inventory"]

    kinds = [("drone_B", L["F05"]["ylabel_drone"], lambda t: t["return_time"]),
             ("battery_B", L["F05"]["ylabel_battery"], lambda t: t["return_time"] + fk.charge_time(t["soc"], full))]
    fig, axes = plt.subplots(2, 1, figsize=(fk.FULL_W, 10.4 * fk.CM), sharex=True, layout="constrained")
    csv_rows, kv = [], {}
    xmax = 1000 * math.ceil(max(k[2](t) for k in kinds for t in tasks) / 1000) + 500
    for ax, (res, ylab, end) in zip(axes, kinds):
        series = {}
        for g in ["all", "G1", "G2"]:
            iv = [(t["start"], end(t)) for t in tasks if g == "all" or group[t["id"]] == g]
            series[g] = concurrency(iv)
        pk = {g: peak_windows(s) for g, s in series.items()}
        # 核对：不分区峰值 = baseline；各组峰值 = 该组配置
        assert pk["all"][0] == q4["baseline_resources"][res]
        for gg in sel["groups"]:
            assert pk[gg["id"]][0] == gg["resources"][res]
        total = pk["G1"][0] + pk["G2"][0]
        assert total == sel["total"][res] and total - inv[res] == sel["shortage"][res]

        for g, col in GCOL.items():
            for a, b in pk[g][1]:
                ax.axvspan(a, b, color=col, alpha=0.13, lw=0, zorder=0)
        xs, ys = zip(*series["all"])
        ax.fill_between(list(xs) + [xmax], list(ys) + [0], step="post", color="#D5DADE", lw=0, zorder=1)
        ax.step(list(xs) + [xmax], list(ys) + [0], where="post", color=fk.C["muted"], lw=1.0, zorder=2)
        for g, ls in [("G1", "-"), ("G2", (0, (4, 1.5)))]:
            st = trim(series[g])
            xs, ys = zip(*st)
            ax.step(xs, ys, where="post", color=GCOL[g], lw=1.6, ls=ls, zorder=3)
        ax.axhline(inv[res], color=fk.C["inventory"], lw=1.2, ls=(0, (6, 2)), zorder=4)
        ax.text(xmax - 60, inv[res] + 0.12, f"{L['common']['inventory']} {inv[res]}", ha="right", va="bottom",
                color=fk.C["inventory"], fontsize=10)
        for g in ["G1", "G2"]:
            a, b = pk[g][1][0]
            ax.text((a + b) / 2, pk[g][0] + 0.12, f"{g} 峰值 {pk[g][0]}", ha="center", va="bottom", fontsize=10,
                    color=GCOL[g] if g == "G1" else "#9A6A00",
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.85))
        ax.text(0.99, 0.97 if res == "drone_B" else 0.97,
                f"组峰值之和 {pk['G1'][0]} + {pk['G2'][0]} = {total}，比库存多 {total - inv[res]}",
                transform=ax.transAxes, ha="right", va="top", fontsize=10,
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=fk.C["grid"], lw=0.6))
        ax.set_ylabel(ylab)
        ax.set_ylim(0, inv[res] + 2.1)
        ax.yaxis.set_major_locator(MultipleLocator(1))
        ax.grid(axis="y", zorder=0)
        ax.set_axisbelow(True)
        for g, s in series.items():
            for t, c in s:
                csv_rows.append({"resource": res, "series": g, "time_s": t, "count_from_time": c})
        kv[res] = {"inventory": inv[res], "peak_all": pk["all"][0], "peak_G1": pk["G1"][0], "peak_G2": pk["G2"][0],
                   "sum_of_group_peaks": total, "shortage": total - inv[res],
                   "G1_peak_windows_s": [[round(a, 3), round(b, 3)] for a, b in pk["G1"][1]],
                   "G2_peak_windows_s": [[round(a, 3), round(b, 3)] for a, b in pk["G2"][1]],
                   "all_peak_windows_s": [[round(a, 3), round(b, 3)] for a, b in pk["all"][1]]}
    axes[-1].set_xlim(0, xmax)
    axes[-1].xaxis.set_major_locator(MultipleLocator(1000))
    axes[-1].set_xlabel(L["common"]["time_s"])
    fk.panel_label(axes[0], "(a)", x=-0.075, y=1.0)
    fk.panel_label(axes[1], "(b)", x=-0.075, y=1.0)
    handles = [Patch(fc="#D5DADE", ec=fk.C["muted"], lw=1.0, label=L["F05"]["all"]),
               Line2D([], [], color=GCOL["G1"], lw=1.6, label=L["F05"]["G1"]),
               Line2D([], [], color=GCOL["G2"], lw=1.6, ls=(0, (4, 1.5)), label=L["F05"]["G2"]),
               Line2D([], [], color=fk.C["inventory"], lw=1.2, ls=(0, (6, 2)), label=L["common"]["inventory"]),
               Patch(fc=GCOL["G1"], alpha=0.13, label="G1 峰值时段"),
               Patch(fc=GCOL["G2"], alpha=0.13, label="G2 峰值时段")]
    fig.legend(handles=handles, loc="outside lower center", ncol=3, columnspacing=1.2, handletextpad=0.4,
               handlelength=1.5)
    fk.write_csv(HERE / f"{STEM}.csv", csv_rows)
    fk.save(fig, HERE, STEM, figure_id="F5",
            caption="两组方案中 B 型机与 B 型电池的并发数",
            section="9.4.5",
            sources=[q3p, q4p, fk.TYPE_XLSX],
            key_values=kv,
            notes="G1 为除 S011 外的 14 个服务区，G2 为 S011（K=2 资源优先方案）。不分区曲线等于两组曲线之和，最大为库存值；两组各自的峰值出现在不同时段，分组后各组需按自身峰值配备，合计比库存多 1 件。")


if __name__ == "__main__":
    main()
