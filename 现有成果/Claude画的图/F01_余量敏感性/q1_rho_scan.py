"""问题一返航余量敏感性：调用附件正式程序（src/q1_engine.py、src/dcore.py）重算。

计算内容
1. 余量 r = 0.20, 0.21, …, 0.40：45 个机型—服务区组合的最大安全载荷（Model.max_payload）；
   两种目标顺序的完整求解（q1_solve），记录架次、能耗与机型构成，不可行时记录原因。
2. 安全载荷曲线：r 以 0.0005 为步长加密；并由正式能耗函数给出每个组合开始受电量限制
   与空载也无法往返的临界余量。
3. 最少架次的全部跳变点：对每个服务区，以正式候选生成函数给出的全部候选返航荷电状态
   作为可能的变化点，在这些点上调用 q1_solve（单服务区视图）二分定位。
4. 两种目标顺序下各服务区最优值的精确分段：从 r=0.20 起求解，所得方案在其最小返航
   荷电状态之前保持最优，越过后在下一个候选阈值处重新求解，直至不可行或 r>0.40。
结果写入同目录 q1_rho_scan.json。只读输入，不修改附件。
"""
import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import copy
import hashlib
import json
import math
import time
from bisect import bisect_right
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "inputs" / "attachment" / "src"
sys.path.insert(0, str(SRC))

RHO_GRID = [round(0.20 + 0.01 * k, 2) for k in range(21)]
RHO_FINE = [round(0.20 + 0.0005 * k, 4) for k in range(401)]
RHO_MAX = 0.40
PRIORITIES = ["sorties_energy", "energy_sorties"]
_M = None


def model():
    global _M
    if _M is None:
        from dcore import Model
        _M = Model()
    return _M


def site_view(m, site):
    v = copy.copy(m)
    v.boxes = {k: b for k, b in m.boxes.items() if b["site"] == site}
    return v


def sites(m):
    return sorted({b["site"] for b in m.boxes.values()})


def thresholds(m, site):
    """该服务区全部候选批次的返航荷电状态（r 不超过该值时候选可行），取 r>=0.20 部分。"""
    from q1_engine import candidates
    cand, _ = candidates(m, site, 0.20)
    vals = sorted({1 - c["energy"] / m.types[c["type"]]["energy"] for c in cand})
    return [t for t in vals if t >= 0.20 - 1e-15]


def call_solve(m, rho, priority):
    """调用正式 q1_solve；求解器因时限未给出解时重试，绝不把超时记为不可行。"""
    from q1_engine import q1_solve
    for attempt in range(4):
        try:
            return q1_solve(m, rho=rho, priority=priority), None
        except (ValueError, RuntimeError) as e:
            msg = str(e)
            if "Time limit" not in msg:
                return None, msg[:200]
    raise RuntimeError(f"多次超时：r={rho} {priority}")


def solve_site(m, site, rho, priority):
    r, err = call_solve(site_view(m, site), rho, priority)
    if r is None:
        return {"feasible": False, "reason": err}
    t = r["tasks"]
    return {"feasible": True, "sorties": r["metrics"]["sorties"], "energy": r["metrics"]["energy"],
            "min_soc": min(x["soc"] for x in t), "types": "".join(sorted(x["type"] for x in t)),
            "batches": [[x["type"], x["boxes"], x["soc"]] for x in t]}


def job_grid(args):
    rho, priority = args
    m = model()
    r, err = call_solve(m, rho, priority)
    if r is None:
        return {"rho": rho, "priority": priority, "feasible": False, "reason": err}
    t = r["tasks"]
    per = {}
    for x in t:
        s = x["order"][0]
        d = per.setdefault(s, {"sorties": 0, "energy": 0.0, "types": ""})
        d["sorties"] += 1
        d["energy"] += x["energy"]
        d["types"] += x["type"]
    return {"rho": rho, "priority": priority, "feasible": True, "metrics": r["metrics"],
            "min_soc": min(x["soc"] for x in t),
            "type_counts": {g: sum(1 for x in t if x["type"] == g) for g in "ABC"},
            "per_site": per}


def job_jumps(site):
    """最少架次随余量的全部跳变点（至 r=0.45 或不可行为止）。"""
    m = model()
    T_all = thresholds(m, site)
    T = [t for t in T_all if t <= 0.45]
    if not T:
        s0 = solve_site(m, site, 0.20, "sorties_energy")
        return {"site": site, "n_thresholds": 0, "value_at_0.20": s0.get("sorties"), "jumps": [], "tail": None,
                "evaluations": 1, "note": "0.20 至 0.45 之间没有候选阈值，最少架次不变"}
    memo = {}

    def f(k):
        if k not in memo:
            s = solve_site(m, site, T[k], "sorties_energy")
            memo[k] = (s["sorties"] if s["feasible"] else math.inf, s)
        return memo[k][0]

    jumps = []

    def search(lo, hi):
        if f(lo) == f(hi):
            return
        if hi == lo + 1:
            jumps.append(lo)
            return
        mid = (lo + hi) // 2
        search(lo, mid)
        search(mid, hi)

    search(0, len(T) - 1)
    out = []
    for k in sorted(jumps):
        last = memo[k][1]
        out.append({"after_r": T[k], "next_threshold": T[k + 1], "from": f(k),
                    "to": (None if f(k + 1) == math.inf else f(k + 1)),
                    "last_feasible_batches": last.get("batches")})
    tail = None
    if f(len(T) - 1) != math.inf and len(T) == len(T_all):
        tail = {"after_r": T[-1], "from": f(len(T) - 1), "to": None, "note": "最后一个候选阈值之后无候选"}
    return {"site": site, "n_thresholds": len(T), "value_at_0.20": f(0), "jumps": out, "tail": tail,
            "evaluations": len(memo)}


def job_trace(args):
    site, priority = args
    m = model()
    T = thresholds(m, site)
    rho = 0.20
    segs = []
    while rho <= RHO_MAX + 1e-12:
        s = solve_site(m, site, rho, priority)
        if not s["feasible"]:
            segs.append({"r_from": rho, "r_to": None, "feasible": False, "reason": s["reason"]})
            break
        hi = s["min_soc"]
        segs.append({"r_from": rho, "r_to": hi, "feasible": True, "sorties": s["sorties"],
                     "energy": s["energy"], "types": s["types"]})
        k = bisect_right(T, max(hi, rho) + 1e-13)
        if k >= len(T):
            segs.append({"r_from": hi, "r_to": None, "feasible": False, "reason": "no candidate above threshold"})
            break
        rho = T[k]
    return {"site": site, "priority": priority, "segments": segs}


def payload_tables(m):
    from dcore import leg
    out = {"grid": {}, "fine": {}, "critical": {}}
    combos = [(g, s) for g in sorted(m.types) for s in sorted(m.nodes) if s != "O01"]
    for g, s in combos:
        tp = m.types[g]

        def e(q):
            return leg(tp, m.geo["O01", s], q)["energy"] + leg(tp, m.geo[s, "O01"], 0)["energy"]
        out["critical"][f"{g}-{s}"] = {"capacity": tp["capacity"], "usable_energy": tp["energy"],
                                        "r_energy_limited_above": 1 - e(tp["capacity"]) / tp["energy"],
                                        "r_unreachable_above": 1 - e(0) / tp["energy"]}
    for rho in RHO_GRID:
        out["grid"][f"{rho:.2f}"] = {f"{g}-{s}": m.max_payload(g, s, rho) for g, s in combos}
    focus = ["B-S008", "C-S002", "C-S003", "C-S004", "C-S008", "C-S012"]
    for rho in RHO_FINE:
        out["fine"][f"{rho:.4f}"] = {k: m.max_payload(k[0], k[2:], rho) for k in focus}
    return out


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    t0 = time.time()
    m = model()
    site_list = sites(m)
    jobs_grid = [(r, p) for r in RHO_GRID for p in PRIORITIES]
    jobs_trace = [(s, p) for s in site_list for p in PRIORITIES]
    with Pool(processes=6) as pool:
        b = pool.map_async(job_jumps, site_list, chunksize=1)
        c = pool.map_async(job_trace, jobs_trace, chunksize=1)
        a = pool.map_async(job_grid, jobs_grid, chunksize=1)
        payload = payload_tables(m)
        part = HERE / "q1_rho_scan_part.json"
        jumps = b.get()
        part.write_text(json.dumps({"min_sortie_jumps": jumps}, ensure_ascii=False, indent=1), encoding="utf-8")
        traces = c.get()
        part.write_text(json.dumps({"min_sortie_jumps": jumps, "value_traces": traces}, ensure_ascii=False, indent=1), encoding="utf-8")
        grid = a.get()
    part.unlink()
    src_files = [SRC / "q1_engine.py", SRC / "dcore.py"] + sorted((SRC.parent / "data" / "original").rglob("*.xlsx")) \
        + sorted((SRC.parent / "data" / "original").rglob("*.tif"))
    out = {
        "program": "附件 src/q1_engine.py 的 q1_solve 与 candidates，src/dcore.py 的 Model.max_payload 与 leg",
        "program_sources": [{"path": p.resolve().relative_to(ROOT).as_posix(), "sha256": digest(p)} for p in src_files],
        "r_grid": RHO_GRID,
        "grid_solutions": grid,
        "min_sortie_jumps": jumps,
        "value_traces": traces,
        "safe_payload": payload,
        "note": "跳变点 after_r 表示余量超过该值（严格大于）后最少架次改变；该值本身仍可取得原架次。",
    }
    (HERE / "q1_rho_scan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("完成，用时", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
