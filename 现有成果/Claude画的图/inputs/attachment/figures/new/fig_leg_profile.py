"""航段 O01→S003 的沿线地形剖面与“爬升—巡航—下降”三阶段航迹示意（读 fig_leg_profile.csv）。"""
import sys
sys.dont_write_bytecode = True
import math
import matplotlib.pyplot as plt
from figstyle import setup, read, save, tidy, COLORS


def main():
    setup()
    rows = read("fig_leg_profile")
    ter = [(float(r["distance_m"]), float(r["altitude_m"])) for r in rows if r["kind"] == "terrain"]
    trk = [(float(r["distance_m"]), float(r["altitude_m"])) for r in rows if r["kind"] == "track"]
    zmax = [float(r["altitude_m"]) for r in rows if r["kind"] == "terrain_max"][0]
    fig, ax = plt.subplots(figsize=(15.5 / 2.54, 3.3))
    fig.subplots_adjust(left=0.11, right=0.97, top=0.95, bottom=0.16)
    xs = [p[0] for p in ter]; zs = [p[1] for p in ter]
    ax.step(xs, zs, where="mid", color="#7A6A58", linewidth=0.8, label="沿线 DEM 地面高程")
    ax.fill_between(xs, 0, zs, step="mid", color="#D8CBB8", alpha=0.6, linewidth=0)
    ax.plot([p[0] for p in trk], [p[1] for p in trk], color=COLORS["A"], linewidth=1.8, label="三阶段航迹")
    ax.axhline(zmax, color="#B65D3B", linestyle="--", linewidth=0.9, label=f"沿线最高地面 {zmax:.1f} m")
    L = trk[-1][0]; cz = trk[1][1]
    ax.annotate("爬升", xy=(0, (trk[0][1] + cz) / 2), xytext=(350, (trk[0][1] + cz) / 2), va="center",
                arrowprops=dict(arrowstyle="->", linewidth=0.6))
    ax.text(L / 2, cz + 12, f"巡航（海拔 {cz:.1f} m，高出沿线最高地面 50 m）", ha="center", va="bottom")
    ax.annotate("下降", xy=(L, (trk[-1][1] + cz) / 2), xytext=(L - 350, (trk[-1][1] + cz) / 2), va="center", ha="right",
                arrowprops=dict(arrowstyle="->", linewidth=0.6))
    ax.set_xlim(-150, L + 150)
    ax.set_ylim(100, math.ceil((cz + 80) / 100) * 100)
    ax.set_xlabel("距 O01 的水平距离 / m")
    ax.set_ylabel("海拔 / m")
    tidy(ax)
    ax.legend(frameon=True, facecolor="white", edgecolor="none", framealpha=0.92, loc="lower right", fontsize=10)
    save(fig, "fig_leg_profile")


if __name__ == "__main__":
    main()
