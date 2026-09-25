"""F4 电池与能源组件使用日历：(a) 问题二 14 块电池；(b) 问题三 14 块电池与 6 个能源组件。

每行一个电池或组件。实心条为任务占用（准备开始至返航），斜线条为按式(15)计算的充电尾段；
能源组件在返航后先经 300 s 周转再充电（灰色条）。数据：results/q2.json、results/q3.json；
充电时长参数取原题表。图中数值与 JSON 中 battery_ready、resource_check 逐项核对。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import math
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import MultipleLocator
from matplotlib.colors import to_rgba

STEM = "fig_energy_calendar"
BAR_H = 0.72
WAIT_TASK = "Q2-022"      # 正文 7.5 节讨论的等待实例
TOL = 1e-9


def tint(c, a=0.28):
    r, g, b, _ = to_rgba(c)
    return (1 - a + a * r, 1 - a + a * g, 1 - a + a * b, 1)


def battery_rows(tasks, full, qid):
    rows = []
    for t in sorted(tasks, key=lambda x: (x["start"], x["id"])):
        ready = t["return_time"] + fk.charge_time(t["soc"], full[t["type"]])
        rows.append({"question": qid, "resource": t["battery"], "kind": t["type"], "task": t["id"],
                     "drone": t["drone"], "start": t["start"], "return": t["return_time"], "soc": t["soc"],
                     "turn_end": t["return_time"], "ready": ready})
    return rows


def component_rows(relays, full, turn):
    rows = []
    for r in sorted(relays, key=lambda x: x["start"]):
        start_charge = r["return_time"] + turn
        ready = start_charge + fk.charge_time(r["soc"], full["R"])
        assert abs(start_charge - r["entity_ready"]) < 1e-9 and abs(ready - r["component_ready"]) < 1e-7
        rows.append({"question": "Q3", "resource": r["component"], "kind": "R", "task": r["id"],
                     "drone": r["drone"], "start": float(r["start"]), "return": r["return_time"], "soc": r["soc"],
                     "turn_end": start_charge, "ready": ready})
    return rows


def find_wait(rows):
    """找出指定任务开始前，其实体已空闲而电池仍在充电的时段。"""
    by_drone = {}
    target = None
    for r in sorted(rows, key=lambda x: x["start"]):
        if r["task"] == WAIT_TASK:
            prev_drone = by_drone.get(r["drone"])
            prev_batt = [x for x in rows if x["resource"] == r["resource"] and x["ready"] <= r["start"] + TOL]
            target = {"task": r["task"], "drone": r["drone"], "battery": r["resource"],
                      "drone_free": prev_drone["return"], "battery_ready": max(x["ready"] for x in prev_batt),
                      "start": r["start"]}
        by_drone[r["drone"]] = r
    target["wait"] = target["start"] - target["drone_free"]
    assert abs(target["battery_ready"] - target["start"]) < 1e-9
    return target


def draw(ax, rows, order, labels_short, L, xmax):
    ypos = {k: i for i, k in enumerate(order)}
    for r in rows:
        y = ypos[r["resource"]]
        col = fk.C["relay"] if r["kind"] == "R" else fk.C[r["kind"]]
        ax.add_patch(Rectangle((r["start"], y - BAR_H / 2), r["return"] - r["start"], BAR_H, fc=col,
                               ec="white", lw=0.4, zorder=3))
        if r["turn_end"] > r["return"]:
            ax.add_patch(Rectangle((r["return"], y - BAR_H / 2), r["turn_end"] - r["return"], BAR_H,
                                   fc="#C9CED2", ec="white", lw=0.4, zorder=3))
        ax.add_patch(Rectangle((r["turn_end"], y - BAR_H / 2), r["ready"] - r["turn_end"], BAR_H,
                               fc=tint(col), ec=col, lw=0.5, hatch="////", zorder=3))
        ax.text((r["start"] + r["return"]) / 2, y, labels_short(r["task"]), ha="center", va="center",
                color="white", fontsize=10, zorder=4)
    ax.set_yticks(range(len(order)), order)
    ax.set_ylim(len(order) - 0.45, -0.55)
    ax.set_xlim(0, xmax)
    ax.xaxis.set_major_locator(MultipleLocator(2000))
    ax.xaxis.set_minor_locator(MultipleLocator(1000))
    ax.grid(axis="x", which="both", zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    kinds = [o.split("-")[0] if "BAT" in o else "R" for o in order]
    for i in range(1, len(order)):
        if kinds[i] != kinds[i - 1]:
            ax.axhline(i - 0.5, color=fk.C["muted"], lw=0.5, ls=(0, (2, 2)), zorder=1)
    for lab, k in zip(ax.get_yticklabels(), kinds):
        lab.set_color(fk.C["relay"] if k == "R" else fk.C[k])


def main():
    fk.setup()
    L = fk.labels()
    q2p, q3p = fk.RESULTS / "q2.json", fk.RESULTS / "q3.json"
    q2, q3 = fk.load_json(q2p), fk.load_json(q3p)
    full = fk.charge_full()
    turn = fk.relay_turnaround()

    r2 = battery_rows(q2["tasks"], full, "Q2")
    r3 = battery_rows(q3["tasks"], full, "Q3") + component_rows(q3["relays"], full, turn)
    # 核对：Q2 battery_ready；Q3 resource_check 中电池与组件的占用区间
    for b, v in q2["battery_ready"].items():
        mine = max(r["ready"] for r in r2 if r["resource"] == b)
        assert abs(mine - v) < 1e-7, (b, mine, v)
    rc = q3["resource_check"]["resources"]
    n_checked = 0
    for r in r3:
        key = ("E/" if r["kind"] == "R" else "B/") + r["resource"]
        match = [iv for iv in rc[key] if iv[2] == r["task"]]
        assert len(match) == 1 and abs(match[0][0] - r["start"]) < 1e-9 and abs(match[0][1] - r["ready"]) < 1e-7, (key, r["task"])
        n_checked += 1
    wait = find_wait(r2)
    assert abs(round(wait["wait"], 3) - 108.936) < 1e-9, wait

    bat_order = [f"{g}-BAT-{i:02d}" for g, n in [("A", 6), ("B", 4), ("C", 4)] for i in range(1, n + 1)]
    comp_order = sorted({r["resource"] for r in r3 if r["kind"] == "R"})
    xmax = 1000 * math.ceil(max(r["ready"] for r in r2 + r3) / 1000)

    h2, h3 = len(bat_order), len(bat_order) + len(comp_order)
    fig = plt.figure(figsize=(fk.FULL_W, 16.6 * fk.CM), layout="constrained")
    gs = fig.add_gridspec(2, 1, height_ratios=[h2, h3])
    ax2 = fig.add_subplot(gs[0])
    ax3 = fig.add_subplot(gs[1], sharex=ax2)
    draw(ax2, r2, bat_order, lambda s: s.replace("Q2-", ""), L, xmax)
    draw(ax3, r3, bat_order + comp_order, lambda s: s.replace("Q3-", ""), L, xmax)
    ax2.tick_params(labelbottom=False)
    ax3.set_xlabel(L["common"]["time_s"])
    fk.panel_label(ax2, "(a) 问题二", x=0.0, y=1.01)
    ax2.texts[-1].set_ha("left")
    fk.panel_label(ax3, "(b) 问题三", x=0.0, y=1.01)
    ax3.texts[-1].set_ha("left")

    # 标出 Q2-022 等待 A-BAT-06 充满的时段
    y = bat_order.index(wait["battery"])
    ax2.add_patch(Rectangle((wait["drone_free"], y - 0.5), wait["wait"], 1.0, fc="none", ec=fk.C["inventory"],
                            lw=1.3, zorder=6))
    ax2.annotate(f"{wait['drone']} 已返回，{wait['task']} 等待\n{wait['battery']} 充满 {wait['wait']:.3f} s",
                 xy=(wait["drone_free"] + wait["wait"], y - 0.5), xytext=(xmax - 150, 1.6),
                 fontsize=10, ha="right", va="center", color=fk.C["inventory"], zorder=7, linespacing=1.25,
                 arrowprops=dict(arrowstyle="->", color=fk.C["inventory"], lw=0.8, shrinkA=2, shrinkB=1,
                                 connectionstyle="arc3,rad=0.15"),
                 bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.95))

    handles = [Patch(fc=fk.C["muted"], ec="white", label=L["F04"]["flight"]),
               Patch(fc=tint(fk.C["muted"]), ec=fk.C["muted"], hatch="////", label=L["F04"]["charge"]),
               Patch(fc="#C9CED2", ec="white", label=L["F04"]["turn"]),
               Patch(fc="none", ec=fk.C["inventory"], lw=1.3, label=L["F04"]["wait"])]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, columnspacing=1.2, handletextpad=0.5)

    csv_rows = []
    for r in r2 + r3:
        csv_rows.append({**r, "charge_or_turn_s": r["ready"] - r["return"]})
    fk.write_csv(HERE / f"{STEM}.csv", csv_rows)
    occ = {}
    for r in r2 + r3:
        k = (r["question"], r["resource"])
        occ.setdefault(k, [0, 0.0])
        occ[k][0] += 1
        occ[k][1] += r["ready"] - r["start"]
    fk.save(fig, HERE, STEM, figure_id="F4",
            caption="电池与能源组件使用日历",
            section="7.5（(a)）与 8.6.1 或附录 D（(b)）",
            sources=[q2p, q3p, fk.TYPE_XLSX, fk.RELAY_XLSX],
            key_values={"wait_example": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in wait.items()},
                        "q2_battery_ready_checked": len(q2["battery_ready"]),
                        "q3_intervals_checked_against_resource_check": n_checked,
                        "charge_full_s": full, "relay_turnaround_s": turn,
                        "use_count_and_occupancy_s": {f"{a}/{b}": [n, round(s, 3)] for (a, b), (n, s) in sorted(occ.items())}},
            notes="条上编号省略题号前缀。电池占用 = [准备开始, 返航 + 式(15)充电时间)；组件占用 = [准备开始, 返航 + 300 s + 充电时间)。等待时段为实体已返回而电池尚未充满的区间。")


if __name__ == "__main__":
    main()
