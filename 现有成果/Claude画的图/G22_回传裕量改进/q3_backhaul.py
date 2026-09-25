"""图22 改进版：六个中继任务的回传裕量下界（原图源 figures/fusion/q3_backhaul.py 的副本修改）。

改动：R-002 的 5.357 dB 使其余柱被压扁，改为断轴（左段 0～1.1 dB，右段 5.2～5.5 dB）；删去图内说明文字。
数据：results/q3.json 的 communication.backhaul_certificates 与 delta_g_db（与原图源相同）。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

STEM = "q3_backhaul"
LEFT = (0, 1.1)
RIGHT = (5.2, 5.5)


def main():
    fk.setup()
    q3p = fk.RESULTS / "q3.json"
    q = fk.load_json(q3p)
    bc = q["communication"]["backhaul_certificates"]
    guard = q["communication"]["delta_g_db"]
    rows = [{"中继架次": r["id"], "回传裕量下界_dB": bc[r["id"]]["margin_lower_db"], "稳健判定门限_dB": guard}
            for r in q["relays"]]
    v = [r["回传裕量下界_dB"] for r in rows]
    assert all(x < LEFT[1] or RIGHT[0] < x < RIGHT[1] for x in v) and min(v) >= guard
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(fk.FULL_W, 6.4 * fk.CM), sharey=True, layout="constrained",
                                 gridspec_kw={"width_ratios": [4.2, 1.3], "wspace": 0.02})
    y = list(range(len(rows)))
    for ax, (lo, hi) in [(a1, LEFT), (a2, RIGHT)]:
        ax.barh(y, v, color=fk.C["A"], height=0.6, zorder=3)
        ax.set_xlim(lo, hi)
        ax.grid(axis="x", zorder=0)
        ax.set_axisbelow(True)
        for yi, x in zip(y, v):
            if lo <= x <= hi:
                ax.text(x + (hi - lo) * 0.012, yi, f"{x:.3f}", va="center", ha="left", fontsize=10, zorder=4)
    a1.axvline(guard, color="#202C33", ls="--", lw=1, zorder=4, label=f"稳健判定门限 {guard:.2f} dB")
    a1.set_yticks(y, [r["中继架次"] for r in rows])
    a1.invert_yaxis()
    a1.xaxis.set_major_locator(MultipleLocator(0.2))
    a2.xaxis.set_major_locator(MultipleLocator(0.1))
    a1.spines["right"].set_visible(False)
    a2.spines["left"].set_visible(False)
    a2.tick_params(axis="y", length=0)
    # 断轴记号
    d = dict(marker=[(-1, -1.6), (1, 1.6)], markersize=8, linestyle="none", color="#657078", mec="#657078",
             mew=0.8, clip_on=False)
    a1.plot([1], [0], transform=a1.transAxes, **d)
    a2.plot([0], [0], transform=a2.transAxes, **d)
    fig.supxlabel("回传链路裕量下界/dB", fontsize=10.5)
    a1.legend(loc="lower right")
    fk.write_csv(HERE / f"{STEM}.csv", rows)
    fk.save(fig, HERE, STEM, figure_id="图22（改进版）",
            caption="六个中继任务的回传裕量下界（横轴在 1.1～5.2 dB 处断开）",
            section="8.6.3", sources=[q3p],
            key_values={"relay_certificates": len(rows), "margins_db": {r["中继架次"]: r["回传裕量下界_dB"] for r in rows},
                        "minimum_backhaul_bound_db": min(v), "guard_db": guard},
            notes="只展示中继至地面站的回传链路下界；R-004 与 R-006 在同一悬停点，下界相同。")


if __name__ == "__main__":
    main()
