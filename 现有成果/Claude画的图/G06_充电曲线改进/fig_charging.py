"""图6 改进版：两阶段等效充电曲线（原图源 figures/src/fig_charging.py 的副本修改）。

改动：由一条曲线（T=1800 s）改为 A、B、C 三型电池与中继能源组件共四条曲线，T 取原题数据
（1800、2400、3000、1800 s）；按论文式(15)计算；删去图内标题（移入图题）。
核对：T=1800 s 的曲线与原图源 CSV 逐点一致。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

STEM = "fig_charging"
SRC_CSV = fk.ORIG_FIG / "src" / f"{STEM}.csv"
SERIES = [("A", "A 型电池", "-"), ("B", "B 型电池", "-"), ("C", "C 型电池", "-"), ("R", "中继能源组件", (0, (3, 2)))]


def main():
    fk.setup()
    full = fk.charge_full()
    assert [full[k] for k in "ABCR"] == [1800.0, 2400.0, 3000.0, 1800.0]
    soc = [round(0.01 * k, 2) for k in range(101)]
    orig = {float(r["soc"]): float(r["charge_seconds"]) for r in fk.read_source_csv(SRC_CSV)}
    assert all(abs(fk.charge_time(s, 1800.0) - orig[s]) < 1e-6 for s in orig)
    col = {"A": fk.C["A"], "B": fk.C["B"], "C": fk.C["C"], "R": fk.C["relay"]}
    fig, ax = plt.subplots(figsize=(fk.FULL_W, 7.8 * fk.CM), layout="constrained")
    rows = []
    for k, name, ls in SERIES:
        y = [fk.charge_time(s, full[k]) for s in soc]
        knee = fk.charge_time(0.9, full[k])
        ax.plot(soc, y, color=col[k], lw=2.4 if k == "A" else 1.5, ls=ls,
                label=f"{name}：T={full[k]:.0f} s，SOC=0.9 时 {knee:.0f} s", zorder=3 if k == "R" else 2)
        if k != "R":
            ax.scatter([0.9], [knee], color=col[k], s=16, zorder=4)
        rows += [{"series": k, "full_time_s": full[k], "soc": s, "charge_seconds": v} for s, v in zip(soc, y)]
    ax.axvline(0.9, color=fk.C["muted"], lw=0.7, ls=(0, (2, 2)), zorder=1)
    ax.set_xlabel("荷电状态 SOC")
    ax.set_ylabel("充满所需时间/s")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 3200)
    ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.yaxis.set_major_locator(MultipleLocator(500))
    fk.grid(ax)
    fig.legend(loc="outside lower center", ncol=2, columnspacing=1.2)
    fk.write_csv(HERE / f"{STEM}.csv", rows)
    fk.save(fig, HERE, STEM, figure_id="图6（改进版）",
            caption="两阶段等效充电曲线（A、B、C 型电池与中继能源组件；SOC=0.9 处为分段点）",
            section="5.4.2", sources=[fk.TYPE_XLSX, fk.RELAY_XLSX, SRC_CSV],
            key_values={"T_full_s": {k: full[k] for k in "ABCR"},
                        "knee_s": {k: fk.charge_time(0.9, full[k]) for k in "ABCR"}},
            notes="A 型电池与中继能源组件的 T 同为 1800 s，两条曲线重合（组件画为虚线叠在 A 型实线上）。")


if __name__ == "__main__":
    main()
