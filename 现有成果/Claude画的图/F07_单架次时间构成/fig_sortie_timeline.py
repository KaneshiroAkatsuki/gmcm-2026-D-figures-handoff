"""F7 单架次时间构成：(a) 运输架次 Q1-001；(b) 中继任务 R-002。

(a) 数据取 results/q1.json 中 Q1-001 的 events（准备装载、爬升、巡航、下降、交接、返航各段），准备与装载按
    原题 C 型工位准备时间与单箱装载时间拆开；电池充电尾段按式(15)由返航荷电状态计算。
(b) 数据取 results/q3.json 中 R-002 的准备开始、到达、服务开始与结束、返航、实体再可用、组件充满时刻；
    准备、建链与周转时间取原题中继机型参数；组件在周转结束后开始充电（与冻结结果 component_ready 一致）。
时间轴以各自任务的准备开始时刻为 0。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import MultipleLocator

STEM = "fig_sortie_timeline"
PH = {"prep": "#C9D1D6", "load": "#98A6AF", "fly": "#56B4E9", "work": "#E8C547", "turn": "#CDB9DE",
      "charge": "#FFFFFF"}
TOL = 1e-6


def fmt(v):
    return f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:.1f}"


def draw_phase_row(ax, y, segs, tiers):
    """segs: [(key, name, t0, t1, color)]；tiers: 每段标签所在层（0 或 1）。"""
    for (key, name, a, b, col), tier in zip(segs, tiers):
        ax.add_patch(Rectangle((a, y - 0.32), b - a, 0.64, fc=col, ec="white", lw=0.6, zorder=3))
        ty = y + 0.55 + 0.95 * tier
        ax.plot([(a + b) / 2] * 2, [y + 0.34, ty - 0.02], color=fk.C["muted"], lw=0.5, zorder=2)
        ax.text((a + b) / 2, ty, f"{name}\n{fmt(b - a)} s", ha="center", va="bottom", fontsize=10,
                linespacing=1.0, zorder=4)


def occ_row(ax, y, a, b, label=None):
    ax.add_patch(Rectangle((a, y - 0.3), b - a, 0.6, fc=fk.C["C"] if label == "C" else fk.C["relay"],
                           ec="none", zorder=3))


def tail(ax, y, a, b, kind):
    if kind == "charge":
        ax.add_patch(Rectangle((a, y - 0.3), b - a, 0.6, fc="white", ec=fk.C["ink"], lw=0.6, hatch="////",
                               zorder=3))
    else:
        ax.add_patch(Rectangle((a, y - 0.3), b - a, 0.6, fc=PH["turn"], ec="none", zorder=3))


def main():
    fk.setup()
    L = fk.labels()["F07"]
    p1, p3 = fk.RESULTS / "q1.json", fk.RESULTS / "q3.json"
    q1, q3 = fk.load_json(p1), fk.load_json(p3)
    typ = fk._sheet(fk.TYPE_XLSX)
    tC = {r[0]: r for r in typ[2:5]}["C"]
    prep_C, load_box = float(tC[10]), float(tC[11])
    rel = fk._sheet(fk.RELAY_XLSX)[2]
    prep_R, link_R, turn_R = float(rel[9]), float(rel[10]), float(rel[11])
    full = fk.charge_full()

    # (a) Q1-001
    t = next(x for x in q1["tasks"] if x["id"] == "Q1-001")
    ev = t["events"]
    assert ev[0]["phase"] == "准备装载" and abs(ev[0]["end"] - (prep_C + load_box * len(t["boxes"]))) < TOL
    hand = next(e for e in ev if e["phase"] == "交接")
    go = [e for e in ev if e["end"] <= hand["start"] + TOL and e["phase"] in ("爬升", "巡航", "下降")]
    back = [e for e in ev if e["start"] >= hand["end"] - TOL]
    assert [e["phase"] for e in go] == ["爬升", "巡航", "下降"] and len(back) == 3
    segs_a = [("prep", L["prep"], 0.0, prep_C, PH["prep"]),
              ("load", L["load"], prep_C, ev[0]["end"], PH["load"])]
    for e, nm in zip(go, [L["climb"], L["cruise"], L["descend"]]):
        segs_a.append(("fly", nm, e["start"], e["end"], PH["fly"]))
    segs_a.append(("work", L["handover"], hand["start"], hand["end"], PH["work"]))
    segs_a.append(("fly", L["return"], back[0]["start"], back[-1]["end"], PH["fly"]))
    ret_a = t["duration"]
    assert abs(back[-1]["end"] - ret_a) < TOL
    chg_a = fk.charge_time(t["soc"], full[t["type"]])
    assert abs(chg_a - 1644.689) < 5e-4 and abs(hand["end"] - hand["start"] - 432) < TOL

    # (b) R-002
    r = next(x for x in q3["relays"] if x["id"] == "R-002")
    s0 = r["start"]
    assert abs(r["arrival"] - (s0 + prep_R + r["flight_out"])) < TOL
    assert abs(r["service_start"] - (r["arrival"] + link_R)) < TOL
    assert abs(r["return_time"] - (r["service_end"] + r["flight_back"])) < TOL
    assert abs(r["entity_ready"] - (r["return_time"] + turn_R)) < TOL
    chg_b = fk.charge_time(r["soc"], full["R"])
    assert abs(r["component_ready"] - (r["entity_ready"] + chg_b)) < TOL
    rr = lambda v: v - s0
    segs_b = [("prep", L["prep"], 0.0, prep_R, PH["prep"]),
              ("fly", L["out"], prep_R, rr(r["arrival"]), PH["fly"]),
              ("work", L["link"], rr(r["arrival"]), rr(r["service_start"]), PH["load"]),
              ("work", L["service"], rr(r["service_start"]), rr(r["service_end"]), PH["work"]),
              ("fly", L["return"], rr(r["service_end"]), rr(r["return_time"]), PH["fly"])]

    fig, axes = plt.subplots(2, 1, figsize=(fk.FULL_W, 11.0 * fk.CM), layout="constrained",
                             gridspec_kw={"height_ratios": [1, 1]})
    rows = []
    # 面板 (a)
    ax = axes[0]
    draw_phase_row(ax, 2, segs_a, [0, 1, 0, 1, 0, 1, 0])
    occ_row(ax, 1, 0, ret_a, "C")
    occ_row(ax, 0, 0, ret_a, "C")
    tail(ax, 0, ret_a, ret_a + chg_a, "charge")
    ax.text(ret_a + chg_a / 2, 0, f"{L['charge']} {chg_a:.3f} s", ha="center", va="center", fontsize=10, zorder=5,
            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none"))
    ax.text(ret_a + 30, 1, f"{L['return_at']} {ret_a:.3f} s", ha="left", va="center", fontsize=10)
    ax.set_yticks([0, 1, 2], [L["battery_C"], L["drone_C"], L["phase"]])
    ax.set_xlim(0, 3400)
    ax.set_ylim(-0.6, 4.35)
    for k, nm, a, b, _ in segs_a:
        rows.append({"panel": "a", "task": "Q1-001", "row": "phase", "item": nm, "start_s": a, "end_s": b, "duration_s": b - a})
    rows += [{"panel": "a", "task": "Q1-001", "row": "drone", "item": "占用", "start_s": 0.0, "end_s": ret_a, "duration_s": ret_a},
             {"panel": "a", "task": "Q1-001", "row": "battery", "item": "占用", "start_s": 0.0, "end_s": ret_a, "duration_s": ret_a},
             {"panel": "a", "task": "Q1-001", "row": "battery", "item": "充电", "start_s": ret_a, "end_s": ret_a + chg_a,
              "duration_s": chg_a, "soc": t["soc"]}]
    # 面板 (b)
    ax = axes[1]
    draw_phase_row(ax, 2, segs_b, [0, 1, 0, 1, 0])
    ret_b, ent_b, cmp_b = rr(r["return_time"]), rr(r["entity_ready"]), rr(r["component_ready"])
    occ_row(ax, 1, 0, ret_b)
    tail(ax, 1, ret_b, ent_b, "turn")
    occ_row(ax, 0, 0, ret_b)
    tail(ax, 0, ret_b, ent_b, "turn")
    tail(ax, 0, ent_b, cmp_b, "charge")
    ax.text(cmp_b + 40, 0, f"{L['charge']} {chg_b:.3f} s", ha="left", va="center", fontsize=10, zorder=5)
    ax.text(ent_b + 40, 1, f"{L['entity_ready']} {ent_b:.3f} s", ha="left", va="center", fontsize=10)
    ax.set_yticks([0, 1, 2], [L["component"], L["entity"], L["phase"]])
    ax.set_xlim(0, 7000)
    ax.set_ylim(-0.6, 4.35)
    for k, nm, a, b, _ in segs_b:
        rows.append({"panel": "b", "task": "R-002", "row": "phase", "item": nm, "start_s": a, "end_s": b, "duration_s": b - a})
    rows += [{"panel": "b", "task": "R-002", "row": "entity", "item": "占用", "start_s": 0.0, "end_s": ret_b, "duration_s": ret_b},
             {"panel": "b", "task": "R-002", "row": "entity", "item": "周转", "start_s": ret_b, "end_s": ent_b, "duration_s": ent_b - ret_b},
             {"panel": "b", "task": "R-002", "row": "component", "item": "占用", "start_s": 0.0, "end_s": ret_b, "duration_s": ret_b},
             {"panel": "b", "task": "R-002", "row": "component", "item": "周转", "start_s": ret_b, "end_s": ent_b, "duration_s": ent_b - ret_b},
             {"panel": "b", "task": "R-002", "row": "component", "item": "充电", "start_s": ent_b, "end_s": cmp_b,
              "duration_s": chg_b, "soc": r["soc"]}]
    for ax, tag in zip(axes, ["(a)", "(b)"]):
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.xaxis.set_major_locator(MultipleLocator(500 if ax is axes[0] else 1000))
        ax.grid(axis="x", zorder=0)
        ax.set_axisbelow(True)
        ax.set_xlabel(L["xlabel"])
        fk.panel_label(ax, tag, x=-0.01, y=0.93)
    handles = [Patch(fc=PH["prep"], label=L["prep"]), Patch(fc=PH["load"], label=f"{L['load']}、{L['link']}"),
               Patch(fc=PH["fly"], label=L["flight"]), Patch(fc=PH["work"], label=f"{L['handover']}、{L['service']}"),
               Patch(fc=fk.C["C"], label=L["occ_C"]), Patch(fc=fk.C["relay"], label=L["occ_R"]),
               Patch(fc=PH["turn"], label=L["turn"]), Patch(fc="white", ec=fk.C["ink"], lw=0.6, hatch="////", label=L["charge"])]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, columnspacing=1.0, handletextpad=0.4)
    fk.write_csv(HERE / f"{STEM}.csv", rows, ["panel", "task", "row", "item", "start_s", "end_s", "duration_s", "soc"])
    fk.save(fig, HERE, STEM, figure_id="F7",
            caption="单架次时间构成：(a) 运输架次 Q1-001；(b) 中继任务 R-002",
            section="5.4.1（同时替代 5.3.4 的表5）",
            sources=[p1, p3, fk.TYPE_XLSX, fk.RELAY_XLSX],
            key_values={"Q1-001": {"prep_s": prep_C, "load_s": ev[0]["end"] - prep_C,
                                   "climb_cruise_descend_s": [e["end"] - e["start"] for e in go],
                                   "handover_s": hand["end"] - hand["start"], "return_s": back[-1]["end"] - back[0]["start"],
                                   "duration_s": ret_a, "flight_time_s": t["flight_time"], "soc": t["soc"],
                                   "charge_s": chg_a, "battery_full_at_s": ret_a + chg_a},
                        "R-002": {"start_abs_s": s0, "prep_s": prep_R, "flight_out_s": r["flight_out"], "link_s": link_R,
                                  "service_s": r["service_end"] - r["service_start"], "flight_back_s": r["flight_back"],
                                  "turnaround_s": turn_R, "soc": r["soc"], "charge_s": chg_b,
                                  "return_rel_s": ret_b, "entity_ready_rel_s": ent_b, "component_ready_rel_s": cmp_b,
                                  "component_ready_abs_s": r["component_ready"]}},
            notes="时间以任务准备开始为 0（R-002 的绝对开始时刻为 2396.423 s）。实心条为实体或能源占用，"
                  "紫色浅条为中继返航后的 300 s 周转，斜线条为按式(15)计算的充电尾段；Q1-001 电池返航即开始充电，"
                  "R-002 的能源组件在周转结束后开始充电。")


if __name__ == "__main__":
    main()
