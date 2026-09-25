"""F1 对账：正式程序重算结果（q1_rho_scan.json）与审核参照值（inputs/review_ref/q1_rho.json）逐项比较。

参照值只用于对账，不进入图中数据。输出同目录 F1_对账记录.md 与 q1_rho_reconcile.json。
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))
import json
import math
import figkit as fk
from fig_q1_rho import global_trace, global_min_sorties, value_at

REF = fk.INPUTS / "review_ref" / "q1_rho.json"


def main():
    scan = fk.load_json(HERE / "q1_rho_scan.json")
    ref = fk.load_json(REF)
    out = {"reference": fk.rel(REF), "reference_sha256": fk.sha256(REF),
           "formal_scan": "F01_余量敏感性/q1_rho_scan.json", "formal_scan_sha256": fk.sha256(HERE / "q1_rho_scan.json")}

    # 1 安全载荷 21×45
    diffs, status_mismatch, n = [], [], 0
    for rk, combos in ref["safe_payload_grid"].items():
        mine = scan["safe_payload"]["grid"][f"{float(rk):.2f}"]
        for k, v in combos.items():
            m = mine[k]["payload"]
            n += 1
            if v is None or m is None:
                if (v is None) != (m is None):
                    status_mismatch.append((rk, k, v, m))
                continue
            diffs.append((abs(v - m), rk, k, v, m))
    diffs.sort(reverse=True)
    out["safe_payload"] = {"compared": n, "max_abs_diff_kg": diffs[0][0] if diffs else 0.0,
                           "max_at": diffs[0][1:3] if diffs else None, "status_mismatch": status_mismatch}

    # 2 跳变点（本次搜索到 0.45 为止）
    jm = {j["site"]: j for j in scan["min_sortie_jumps"]}
    jrows, jmax = [], 0.0
    for site, lst in ref["min_sortie_jumps"].items():
        mine = [(x["after_r"], x["from"], x["to"]) for x in jm[site]["jumps"]]
        theirs = [(x["after_rho"], x["from_"], None if x["to"] in (None, math.inf) or x["to"] == float("inf") else x["to"])
                  for x in lst if x["after_rho"] <= 0.45]
        same_len = len(mine) == len(theirs)
        d = max((abs(a[0] - b[0]) for a, b in zip(mine, theirs)), default=0.0)
        same_steps = same_len and all(a[1] == b[1] and a[2] == b[2] for a, b in zip(mine, theirs))
        jmax = max(jmax, d)
        jrows.append({"site": site, "formal": len(mine), "reference": len(theirs), "max_abs_diff": d,
                      "same_steps": same_steps})
    out["jumps"] = {"per_site": jrows, "max_abs_diff": jmax, "all_same": all(r["same_steps"] for r in jrows)}

    # 3 两种目标顺序的最优值
    tr = {p: global_trace(scan["value_traces"], p) for p in ["sorties_energy", "energy_sorties"]}
    srows = []
    for rk, v in ref["rho_scan"].items():
        r = float(rk)
        for p, key in [("sorties_energy", "sorties_first"), ("energy_sorties", "energy_first")]:
            s = value_at(tr[p], r)
            t = v[key]
            if t is None:
                srows.append({"r": rk, "order": key, "formal": None if s[2] is None else [s[2], s[3]],
                              "reference": None, "match": s[2] is None})
            else:
                ok = s[2] == t["sorties"] and abs(s[3] - t["energy"]) < 1e-9
                srows.append({"r": rk, "order": key, "formal": [s[2], s[3]], "reference": [t["sorties"], t["energy"]],
                              "match": ok, "energy_diff": abs(s[3] - t["energy"])})
    out["optima"] = {"rows": srows, "all_match": all(r["match"] for r in srows)}
    (HERE / "q1_rho_reconcile.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    sf, _ = global_min_sorties(scan["min_sortie_jumps"])
    md = ["# F1 对账记录（待与 M2 正式重算结果核对）", "",
          "- 正式程序重算：`q1_rho_scan.py` 调用附件 `src/q1_engine.py`（q1_solve、candidates）与 `src/dcore.py`（Model.max_payload、leg）。",
          f"- 审核参照：`{out['reference']}`（SHA-256 `{out['reference_sha256']}`），只用于对账，不进入图中数据。",
          f"- 重算结果：`{out['formal_scan']}`（SHA-256 `{out['formal_scan_sha256']}`）。", "",
          "## 1 安全载荷（21 个余量 × 45 个组合）", "",
          f"- 比较 {n} 项；最大绝对差 {out['safe_payload']['max_abs_diff_kg']:.3e} kg（{out['safe_payload']['max_at']}）；"
          f"可达/不可达状态不一致 {len(status_mismatch)} 项。", "",
          "## 2 最少架次跳变点（逐服务区，搜索到 r=0.45）", "",
          "| 服务区 | 正式程序个数 | 参照个数 | 最大差 | 架次变化一致 |", "|---|---|---|---|---|"]
    for r in jrows:
        md.append(f"| {r['site']} | {r['formal']} | {r['reference']} | {r['max_abs_diff']:.3e} | {'是' if r['same_steps'] else '否'} |")
    md += ["", "全题最少架次（正式程序，r 取 0.20～0.40）：", "", "| r 区间 | 最少架次 |", "|---|---|"]
    for lo, hi, k in sf:
        md.append(f"| ({lo:.9f}, {hi:.9f}] | {'不可行' if k is None else k} |".replace("(0.200000000", "[0.200000000"))
    md += ["", "## 3 两种目标顺序的最优值", "", "| r | 目标顺序 | 正式程序（架次 / kWh） | 参照（架次 / kWh） | 一致 |", "|---|---|---|---|---|"]
    for r in srows:
        f_ = "不可行" if r["formal"] is None else f"{r['formal'][0]} / {r['formal'][1]:.9f}"
        t_ = "不可行" if r["reference"] is None else f"{r['reference'][0]} / {r['reference'][1]:.9f}"
        md.append(f"| {r['r']} | {r['order']} | {f_} | {t_} | {'是' if r['match'] else '否'} |")
    md += ["", "## 结论", "",
           f"- 安全载荷：{'全部一致' if not status_mismatch and out['safe_payload']['max_abs_diff_kg'] < 1e-9 else '存在差异，见上表'}。",
           f"- 跳变点：{'位置与架次变化全部一致' if out['jumps']['all_same'] and jmax < 1e-12 else '存在差异，见上表'}（最大差 {jmax:.3e}）。",
           f"- 最优值：{'全部一致' if out['optima']['all_match'] else '存在差异，见上表'}。",
           "- 上述数值仍须与论文修改方按 M2 在独立目录重算的结果再核对一次；如有差异，以正式程序在干净副本中的输出为准并重绘 F1。", ""]
    (HERE / "F1_对账记录.md").write_text("\n".join(md), encoding="utf-8")
    print("对账完成：", out["safe_payload"]["max_abs_diff_kg"], jmax, out["optima"]["all_match"])


if __name__ == "__main__":
    main()
