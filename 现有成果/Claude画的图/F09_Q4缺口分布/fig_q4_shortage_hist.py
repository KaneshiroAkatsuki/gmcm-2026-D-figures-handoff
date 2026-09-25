"""F9 问题四缺口件数分布：K=2、K=3 全部分区方案按缺口件数计数（对数纵轴）。

数据：results/q4.json 的 enumeration_statistics（主口径，跨组中继整任务复制）；
      results/q4_no_copy_sensitivity.json 的 enumeration_statistics（禁止复制口径），以空心菱形叠加。
绘图前核对：各直方图计数之和等于枚举总数，且等于第二类 Stirling 数 S(14,K)、S(4,K)；
最小缺口与 selected 方案的缺口合计一致。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import figkit as fk
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import LogLocator, MultipleLocator, NullFormatter

STEM = "fig_q4_shortage_hist"
BAR = "#9DB4C0"
HIGHLIGHT = "#D55E00"


def stirling2(n, k):
    s = [[0] * (k + 1) for _ in range(n + 1)]
    s[0][0] = 1
    for i in range(1, n + 1):
        for j in range(1, k + 1):
            s[i][j] = j * s[i - 1][j] + s[i - 1][j - 1]
    return s[n][k]


def main():
    fk.setup()
    L = fk.labels()["F09"]
    p_main, p_nc = fk.RESULTS / "q4.json", fk.RESULTS / "q4_no_copy_sensitivity.json"
    q4, nc = fk.load_json(p_main), fk.load_json(p_nc)
    n_units, n_units_nc = len(q4["components"]), len(nc["components"])
    assert (n_units, n_units_nc) == (14, 4)

    fig, axes = plt.subplots(1, 2, figsize=(fk.FULL_W, 6.6 * fk.CM), layout="constrained",
                             gridspec_kw={"width_ratios": [17, 27]})
    rows, kv = [], {}
    for ax, K, tag in zip(axes, [2, 3], ["(a)", "(b)"]):
        st = next(s for s in q4["enumeration_statistics"] if s["K"] == K)
        sn = next(s for s in nc["enumeration_statistics"] if s["K"] == K)
        h = {int(k): v for k, v in st["shortage_units_histogram"].items()}
        hn = {int(k): v for k, v in sn["shortage_units_histogram"].items()}
        assert sum(h.values()) == st["enumerated_partitions"] == stirling2(n_units, K)
        assert sum(hn.values()) == sn["enumerated_partitions"] == stirling2(n_units_nc, K)
        sel = next(s for s in q4["selected"] if s["K"] == K)
        seln = next(s for s in nc["selected"] if s["K"] == K)
        xmin, xmin_nc = min(h), min(hn)
        assert xmin == sum(sel["shortage"].values()) and xmin_nc == sum(seln["shortage"].values())

        xs = sorted(h)
        ax.bar(xs, [h[x] for x in xs], width=0.8, color=[HIGHLIGHT if x == xmin else BAR for x in xs],
               edgecolor="white", linewidth=0.4, zorder=2)
        xn = sorted(hn)
        ax.scatter(xn, [hn[x] for x in xn], marker="D", s=22, facecolor="white", edgecolor=fk.C["ink"],
                   linewidth=0.9, zorder=4)
        ax.set_yscale("log")
        ax.set_ylim(0.6, max(h.values()) * 40)
        ax.yaxis.set_major_locator(LogLocator(base=10, numticks=10))
        ax.yaxis.set_minor_locator(LogLocator(base=10, subs="auto", numticks=10))
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.tick_params(axis="y", which="minor", length=1.8, width=0.4)
        ax.set_xlim(min(xs + xn) - 0.8, max(xs + xn) + 0.8)
        ax.xaxis.set_major_locator(MultipleLocator(2 if K == 2 else 4))
        ax.set_xlabel(L["xlabel"])
        ax.grid(axis="y", which="major", zorder=0)
        ax.set_axisbelow(True)
        ax.text(0.02, 0.98, f"K={K}，{L['total']} {st['enumerated_partitions']}", transform=ax.transAxes,
                ha="left", va="top", fontsize=10)
        ax.text(0.02, 0.86, f"{L['min']} {xmin} 件：{h[xmin]} 个方案", transform=ax.transAxes,
                ha="left", va="top", fontsize=10, color=HIGHLIGHT)
        fk.panel_label(ax, tag, x=0.0, y=1.03)
        for x in sorted(set(xs) | set(xn)):
            rows.append({"K": K, "shortage_units": x, "partitions_main": h.get(x, 0), "partitions_no_copy": hn.get(x, 0)})
        kv[f"K{K}"] = {"enumerated_main": st["enumerated_partitions"], "enumerated_no_copy": sn["enumerated_partitions"],
                       "min_shortage_main": xmin, "count_at_min_main": h[xmin],
                       "min_shortage_no_copy": xmin_nc, "count_at_min_no_copy": hn[xmin_nc],
                       "max_shortage_main": max(h)}
    axes[0].set_ylabel(L["ylabel"])
    handles = [Patch(fc=BAR, label=L["main"]), Patch(fc=HIGHLIGHT, label=L["min"]),
               Line2D([], [], marker="D", ls="none", mfc="white", mec=fk.C["ink"], markersize=5, label=L["no_copy"])]
    fig.legend(handles=handles, loc="outside lower center", ncol=3, columnspacing=1.5, handletextpad=0.4)
    fk.write_csv(HERE / f"{STEM}.csv", rows)
    fk.save(fig, HERE, STEM, figure_id="F9",
            caption="问题四各分区方案的缺口件数分布（纵轴为对数刻度）",
            section="9.3.3（替代表14）",
            sources=[p_main, p_nc],
            key_values=kv,
            notes="柱为主口径（14 个不可拆单元，跨组中继整任务复制）的全部分区方案；空心菱形为禁止复制口径（4 个单元）。"
                  "K=2 共 8191 个方案，最小缺口 2 件的 3 个；K=3 共 788970 个方案，最小缺口 4 件的 4 个；"
                  "禁止复制口径 K=2、K=3 分别只有 7、6 个方案，最小缺口 2、6 件。")


if __name__ == "__main__":
    main()
