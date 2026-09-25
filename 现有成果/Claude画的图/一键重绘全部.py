"""在本文件夹（或其完整副本）中运行，重绘全部新增图与改进图。

用法：
    python 一键重绘全部.py              # 只重绘，约 1 分钟
    python 一键重绘全部.py --recompute  # 先调用附件正式 q1 程序重算 F1 的余量扫描（约 10–20 分钟），再重绘
只读 inputs/ 中的数据副本；只在各图文件夹内写 PNG、SVG、CSV 与 meta.json。不求解其他问题，不生成 PDF。
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def scripts():
    out = []
    for d in sorted(p for p in ROOT.iterdir() if p.is_dir() and p.name[:1] in "FG" and p.name[1:3].isdigit()):
        out += sorted(d.glob("fig_*.py"))
    return out


def run(p):
    print(f"[重绘] {p.parent.name}/{p.name}", flush=True)
    subprocess.run([sys.executable, "-B", p.name], cwd=p.parent, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recompute", action="store_true", help="先重算 F1 余量扫描")
    a = ap.parse_args()
    if a.recompute:
        f1 = ROOT / "F01_余量敏感性"
        subprocess.run([sys.executable, "-B", "q1_rho_scan.py"], cwd=f1, check=True)
        subprocess.run([sys.executable, "-B", "q1_rho_reconcile.py"], cwd=f1, check=True)
    todo = scripts()
    for p in todo:
        run(p)
    print(f"完成：共重绘 {len(todo)} 幅图。")


if __name__ == "__main__":
    main()
