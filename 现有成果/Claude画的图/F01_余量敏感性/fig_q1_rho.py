"""F1 问题一返航余量敏感性（两联）。

数据：同目录 q1_rho_scan.json（由 q1_rho_scan.py 调用附件正式程序 src/q1_engine.py、src/dcore.py 重算）。
(a) 基准余量下受电量限制的 6 个机型—服务区组合的最大安全载荷随余量的变化；横线为机型载重上限，
    竖线为 A 型首次受电量限制的余量。
(b) 最少架次的阶梯线（全部跳变点为精确值）；副轴为两种目标顺序的总能耗（逐服务区精确分段求和）。
    阴影为单点往返已无法送完全部货箱的余量区间。
绘图前核对：r=0.20 的结果与冻结 results/q1.json、q1_energy_first.json 一致（架次相同，能耗差只允许浮点舍入量级，差值写入 meta）；网格点上完整求解与分段结果一致；
由跳变点得到的最少架次与架次优先分段结果一致。
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

STEM = "fig_q1_rho"
R0, R1 = 0.20, 0.40
FOCUS = ["B-S008", "C-S002", "C-S003", "C-S004", "C-S008", "C-S012"]
BUNDLE = ["C-S002", "C-S003", "C-S012"]
E_COL = {"sorties_energy": "#3D697A", "energy_sorties": "#CB8E3C"}
E_LS = {"sorties_energy": (0, (5, 2)), "energy_sorties": (0, (1.5, 1.2))}
CURVE_LS = {"B-S008": (0, (5, 1.5)), "C-S002": "-", "C-S003": "-", "C-S012": "-", "C-S004": (0, (6, 1.5, 1.5, 1.5)),
            "C-S008": (0, (1.2, 1.2))}


def global_min_sorties(jumps):
    """由各服务区跳变点合成全题最少架次的分段函数 [(r_lo, r_hi, n)]，n=None 表示不可行。"""
    total = sum(j["value_at_0.20"] for j in jumps)
    ev = []
    for j in jumps:
        for x in j["jumps"]:
            ev.append((x["after_r"], j["site"], x["from"], x["to"]))
        if j.get("tail"):
            ev.append((j["tail"]["after_r"], j["site"], j["tail"]["from"], None))
    ev.sort()
    segs, lo, cur = [], R0, total
    for r, site, a, b in ev:
        if r >= R1:
            break
        segs.append((lo, r, cur))
        lo = r
        cur = None if (cur is None or b is None) else cur + (b - a)
        if cur is None:
            break
    segs.append((lo, R1, cur))
    return segs, ev


def global_trace(traces, priority):
    """把各服务区的最优值分段 (前一上端, r_to] 求和，得到全题分段 [(r_lo, r_hi, sorties, energy)]。"""
    per = {}
    for t in traces:
        if t["priority"] != priority:
            continue
        segs, prev = [], R0
        for s in t["segments"]:
            if s["feasible"]:
                segs.append((prev, s["r_to"], s["sorties"], s["energy"]))
                prev = s["r_to"]
            else:
                segs.append((prev, math.inf, None, None))
                break
        per[t["site"]] = segs
    cuts = sorted({R0, R1} | {b for segs in per.values() for (_, b, _, _) in segs if R0 < b < R1})
    out = []
    for lo, hi in zip(cuts, cuts[1:]):
        mid = (lo + hi) / 2
        n, e = 0, 0.0
        for segs in per.values():
            seg = next(s for s in segs if s[0] < mid <= s[1] or (s[0] == R0 and mid <= s[1]))
            if seg[2] is None:
                n = e = None
                break
            n += seg[2]
            e += seg[3]
        out.append((lo, hi, n, e))
    merged = []
    for s in out:
        if merged and merged[-1][2] == s[2] and (merged[-1][3] == s[3] or (s[3] is not None and merged[-1][3] is not None
                                                                          and abs(merged[-1][3] - s[3]) < 1e-12)):
            merged[-1] = (merged[-1][0], s[1], s[2], s[3])
        else:
            merged.append(s)
    return merged


def value_at(segs, r):
    for s in segs:
        if (s[0] < r <= s[1]) or (r == R0 and s[0] == R0):
            return s
    raise ValueError(r)


def main():
    fk.setup()
    L = fk.labels()
    scan_p = HERE / "q1_rho_scan.json"
    scan = fk.load_json(scan_p)
    q1p, q1ep = fk.RESULTS / "q1.json", fk.RESULTS / "q1_energy_first.json"
    q1, q1e = fk.load_json(q1p), fk.load_json(q1ep)
    pay = scan["safe_payload"]

    # ---------- 核对 ----------
    grid = {(g["rho"], g["priority"]): g for g in scan["grid_solutions"]}
    g0, g0e = grid[(0.2, "sorties_energy")], grid[(0.2, "energy_sorties")]
    assert g0["metrics"]["sorties"] == q1["metrics"]["sorties"] == 18
    frozen_diff = {"sorties_energy": g0["metrics"]["energy"] - q1["metrics"]["energy"]}
    assert abs(frozen_diff["sorties_energy"]) < 1e-9
    assert g0e["metrics"]["sorties"] == q1e["metrics"]["sorties"] == 19
    frozen_diff["energy_sorties"] = g0e["metrics"]["energy"] - q1e["metrics"]["energy"]
    assert abs(frozen_diff["energy_sorties"]) < 1e-9
    base_csv = fk.ATTACH / "data" / "q1_safe_payload_rho020.csv"
    sorties_fn, events = global_min_sorties(scan["min_sortie_jumps"])
    tr = {p: global_trace(scan["value_traces"], p) for p in ["sorties_energy", "energy_sorties"]}
    checked = 0
    for (rho, p), g in grid.items():
        s = value_at(tr[p], rho)
        if g["feasible"]:
            assert s[2] == g["metrics"]["sorties"] and abs(s[3] - g["metrics"]["energy"]) < 1e-9, (rho, p, s, g["metrics"])
        else:
            assert s[2] is None, (rho, p, s)
        checked += 1
    for lo, hi, n in sorties_fn:
        mid = (lo + hi) / 2
        assert value_at(tr["sorties_energy"], mid)[2] == n, (lo, hi, n)

    crit = pay["critical"]
    a_on = min(((v["r_energy_limited_above"], k) for k, v in crit.items() if k.startswith("A-")))
    r_inf = next(lo for lo, hi, n in sorties_fn if n is None)
    step18 = next(hi for lo, hi, n in sorties_fn if n == 18)

    # ---------- 绘图 ----------
    fig, (axa, axb) = plt.subplots(1, 2, figsize=(fk.FULL_W, 9.4 * fk.CM), layout="constrained")
    fig.get_layout_engine().set(wspace=0.10)
    rs = sorted(float(k) for k in pay["fine"])
    rows = []
    for combo in FOCUS:
        xs, ys = [], []
        for r in rs:
            v = pay["fine"][f"{r:.4f}"][combo]
            if v["payload"] is None:
                break
            xs.append(r)
            ys.append(v["payload"])
            rows.append({"panel": "a", "series": combo, "r": r, "value": v["payload"], "status": v["status"]})
        g = combo[0]
        axa.plot(xs, ys, color=fk.C[g], lw=1.5 if combo not in BUNDLE else 1.1, zorder=3, ls=CURVE_LS[combo])
    for g, cap in [("A", 25), ("B", 30), ("C", 80)]:
        assert all(v["capacity"] == cap for k, v in crit.items() if k.startswith(g + "-"))
        axa.axhline(cap, color=fk.C[g], lw=0.8, ls=(0, (1.5, 1.5)), zorder=2)
    for g, cap, dy in [("C", 80, 0), ("B", 30, 1.2), ("A", 25, -1.2)]:
        axa.text(R1 + 0.004, cap + dy, f"{g} {cap}", ha="left", va="center", fontsize=10, color=fk.C[g], clip_on=False)
    axa.plot([a_on[0], a_on[0]], [0, 25], color=fk.C["A"], lw=1.0, ls=(0, (4, 2)), zorder=2)
    axa.text(a_on[0] + 0.003, 5.0, f"{fk.labels()['sym']['r']}={a_on[0]:.6f}",
             fontsize=10, ha="left", va="center", color=fk.C["A"], linespacing=1.2)
    axa.axhline(14, color=fk.C["muted"], lw=0.7, ls=(0, (3, 2)), zorder=1)
    axa.text(R0 + 0.003, 14.6, "单箱饮用水 14 kg", fontsize=10, color=fk.C["muted"], va="bottom",
             bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.8), zorder=4)
    axa.axvspan(r_inf, R1, color="#E6E9EC", zorder=0, lw=0, hatch="///", ec="#C3CAD0")
    axa.set_xlim(R0, R1)
    axa.set_ylim(0, 88)
    axa.xaxis.set_major_locator(MultipleLocator(0.05))
    axa.yaxis.set_major_locator(MultipleLocator(20))
    axa.set_xlabel(L["F01"]["xlabel"])
    axa.set_ylabel(L["F01"]["ylabel_payload"])
    axa.grid(axis="y")
    axa.set_axisbelow(True)

    # (b)
    xs, ys = [], []
    for lo, hi, n in sorties_fn:
        if n is None:
            break
        xs += [lo, hi]
        ys += [n, n]
        rows.append({"panel": "b", "series": "min_sorties", "r": lo, "r_to": hi, "value": n, "status": "(r_lo, r_hi]"})
    axb.plot(xs, ys, color=fk.C["ink"], lw=1.6, zorder=4, drawstyle="default")
    axb.axvspan(r_inf, R1, color="#E6E9EC", zorder=0, lw=0, hatch="///", ec="#C3CAD0")
    axb.text((r_inf + R1) / 2, 17.2, L["F01"]["infeasible"], ha="center", va="bottom", fontsize=10,
             rotation=90, color=fk.C["muted"])
    axb.scatter([step18], [18], s=26, color=fk.C["inventory"], zorder=6)
    axb.annotate(f"{fk.labels()['sym']['r']}={step18:.6f}", (step18, 18), xytext=(7, -4), textcoords="offset points",
                 fontsize=10, color=fk.C["inventory"], va="top")
    for lo, hi, n in sorties_fn:
        if n in (18, 19, 20):
            axb.text((lo + hi) / 2, n + 0.25, str(n), ha="center", va="bottom", fontsize=10)
    axb.annotate("21～25", (0.3425, 23.0), xytext=(0.305, 26.6), ha="center", va="center", fontsize=10,
                 arrowprops=dict(arrowstyle="-", lw=0.6, color=fk.C["muted"], shrinkA=2, shrinkB=2))
    axb.set_xlim(R0, R1)
    axb.set_ylim(16.5, 28.5)
    axb.yaxis.set_major_locator(MultipleLocator(2))
    axb.xaxis.set_major_locator(MultipleLocator(0.05))
    axb.set_xlabel(L["F01"]["xlabel"])
    axb.set_ylabel(L["F01"]["ylabel_sorties"])
    axb.grid(axis="y")
    axb.set_axisbelow(True)
    ax2 = axb.twinx()
    ax2.spines["right"].set_visible(True)
    ekv = {}
    for p in ["sorties_energy", "energy_sorties"]:
        ex, ey = [], []
        for lo, hi, n, e in tr[p]:
            if n is None:
                break
            ex += [lo, hi]
            ey += [e, e]
            rows.append({"panel": "b", "series": f"energy_{p}", "r": lo, "r_to": hi, "value": e,
                         "status": f"sorties={n}"})
        ax2.plot(ex, ey, color=E_COL[p], lw=1.4, ls=E_LS[p], zorder=3)
        ekv[p] = {"r_0.20": [tr[p][0][2], tr[p][0][3]], "last_feasible": [tr[p][[i for i, s in enumerate(tr[p]) if s[2] is not None][-1]][1]],
                  "segments": len([s for s in tr[p] if s[2] is not None])}
    ax2.set_ylim(50, 86)
    ax2.set_ylabel(L["F01"]["ylabel_energy"])
    ax2.yaxis.set_major_locator(MultipleLocator(5))
    fk.panel_label(axa, "(a)", x=-0.02, y=1.01)
    fk.panel_label(axb, "(b)", x=-0.02, y=1.01)

    handles = [Line2D([], [], color=fk.C["B"], lw=1.5, ls=CURVE_LS["B-S008"], label="B-S008"),
               Line2D([], [], color=fk.C["C"], lw=1.1, ls="-", label="C-S002、S003、S012"),
               Line2D([], [], color=fk.C["C"], lw=1.5, ls=CURVE_LS["C-S004"], label="C-S004"),
               Line2D([], [], color=fk.C["C"], lw=1.5, ls=CURVE_LS["C-S008"], label="C-S008"),
               Line2D([], [], color=fk.C["ink"], lw=1.6, label=L["F01"]["sorties_step"]),
               Line2D([], [], color=E_COL["sorties_energy"], lw=1.4, ls=E_LS["sorties_energy"], label=L["F01"]["energy_sf"]),
               Line2D([], [], color=E_COL["energy_sorties"], lw=1.4, ls=E_LS["energy_sorties"], label=L["F01"]["energy_ef"]),
               Line2D([], [], color=fk.C["muted"], lw=0.8, ls=(0, (1.5, 1.5)), label="载重上限（右端数值，色同机型）"),
               Line2D([], [], color=fk.C["A"], lw=1.0, ls=(0, (4, 2)), label=L["F01"]["a_onset"].format(combo=a_on[1])),
               Patch(fc="#E6E9EC", ec="#C3CAD0", hatch="///", label=L["F01"]["infeasible"])]
    fig.legend(handles=handles, loc="outside lower center", ncol=3, columnspacing=1.2, handletextpad=0.4)

    fk.write_csv(HERE / f"{STEM}.csv", rows, ["panel", "series", "r", "r_to", "value", "status"])
    jump_list = [{"after_r": r, "site": s, "from": a, "to": b} for r, s, a, b in events if r < R1]
    fk.save(fig, HERE, STEM, figure_id="F1",
            caption="返航安全余量对安全载荷与组批结果的影响",
            section="6.4",
            sources=[scan_p, q1p, q1ep, base_csv] + [fk.ROOT / x["path"] for x in scan["program_sources"]],
            key_values={"r_A_energy_limited_onset": {"r": a_on[0], "combo": a_on[1]},
                        "min_sorties_18_until": step18,
                        "single_trip_infeasible_after": r_inf,
                        "min_sorties_function": [[lo, hi, n] for lo, hi, n in sorties_fn],
                        "jumps_within_range": jump_list,
                        "energy": ekv,
                        "grid_points_cross_checked": checked,
                        "energy_minus_frozen_at_0.20_kWh": frozen_diff,
                        "payload_at_0.20": {k: pay["grid"]["0.20"][k]["payload"] for k in FOCUS},
                        "energy_limited_combos": {r: sum(1 for k, v in crit.items()
                                                         if v["r_energy_limited_above"] < float(r) <= v["r_unreachable_above"])
                                                  for r in ["0.20", "0.25", "0.30", "0.35", "0.40"]},
                        "unreachable_combos": {r: sorted(k for k, v in crit.items() if float(r) > v["r_unreachable_above"])
                                               for r in ["0.20", "0.25", "0.30", "0.35", "0.40"]}},
            notes="（待与 M2 正式重算结果核对）全部数值由附件正式程序重算：安全载荷用 Model.max_payload（60 次二分），"
                  "跳变点在正式候选生成函数给出的全部候选返航荷电状态处调用 q1_solve 二分定位；能耗曲线为各服务区最优值精确分段之和。"
                  "C-S002、C-S003、C-S012 三条曲线相距很近，用同一线型；各曲线以线型区分，见图例。")


if __name__ == "__main__":
    main()
