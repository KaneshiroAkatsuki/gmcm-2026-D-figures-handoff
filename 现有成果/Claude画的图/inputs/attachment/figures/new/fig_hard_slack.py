"""问题二、问题三中 31 个硬时限货箱的交付完成时刻与截止时刻（读 fig_hard_slack.csv）。"""
import sys
sys.dont_write_bytecode = True
import matplotlib.pyplot as plt
from figstyle import setup, read, save, tidy, COLORS


def main():
    setup()
    rows = read("fig_hard_slack")
    fig, axes = plt.subplots(1, 2, figsize=(15.5 / 2.54, 4.0), sharey=True)
    fig.subplots_adjust(left=0.12, right=0.98, top=0.78, bottom=0.17, wspace=0.12)
    for ax, (plan, title) in zip(axes, (("q2", "(a) 问题二方案"), ("q3", "(b) 问题三方案"))):
        sub = [r for r in rows if r["plan"] == plan]
        assert len(sub) == 31
        for due, mk in ((3600, "o"), (7200, "s"), (10800, "^")):
            pts = [r for r in sub if abs(float(r["deadline_s"]) - due) < 1e-9]
            ax.scatter([float(r["deadline_s"]) for r in pts], [float(r["delivery_s"]) for r in pts],
                       marker=mk, s=26, facecolor="none", edgecolor=COLORS["A"], linewidth=0.9,
                       label=f"截止 {due} s（{len(pts)} 箱）")
        ax.plot([3000, 11400], [3000, 11400], color="#B65D3B", linestyle="--", linewidth=0.9, label="送达 = 截止")
        worst = min(sub, key=lambda r: float(r["slack_s"]))
        ax.annotate(f"最小裕量 {float(worst['slack_s']):.3f} s\n{worst['box']}\n{worst['task']}",
                    xy=(float(worst["deadline_s"]), float(worst["delivery_s"])), xytext=(4800, 7100),
                    fontsize=10, bbox=dict(facecolor="white", edgecolor="none", alpha=0.94, pad=1.5), arrowprops=dict(arrowstyle="->", linewidth=0.6))
        ax.set_xlim(2800, 11600); ax.set_ylim(0, 11400)
        ax.set_xticks([3600, 7200, 10800])
        ax.set_yticks([0, 3600, 7200, 10800])
        ax.set_xlabel("硬时限 / s")
        ax.set_title(title, fontsize=10.5, loc="left")
        tidy(ax)
    axes[0].set_ylabel("交付完成时刻 / s")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, ncol=2, frameon=False, loc="upper center", bbox_to_anchor=(0.54, 1.0), fontsize=10,
               columnspacing=1.0, handletextpad=0.3)
    save(fig, "fig_hard_slack")


if __name__ == "__main__":
    main()
