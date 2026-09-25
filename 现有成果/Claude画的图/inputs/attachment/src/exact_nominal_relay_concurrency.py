import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from pathlib import Path
from decimal import Decimal as D,localcontext
from collections import defaultdict
import argparse,hashlib,json


def run(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    intervals=[(D(x['start_exact_decimal']),D(x['end_exact_decimal']),x['task'],x['relay']) for x in data['intervals'] if x['mode']=='relay']
    points=defaultdict(list)
    for x in data['boundary_points']:
        points[D(x['time_exact_decimal'])].append((x['task'],x['relay'] if x['mode']=='relay' else ''))
    times=sorted({t for a,b,task,rid in intervals for t in [a,b]}|set(points))
    maxima={};errors=[]
    def evaluate(t,kind):
        assignment={}
        for a,b,task,rid in intervals:
            if a<t<b:
                if task in assignment and assignment[task]!=rid:errors.append(dict(kind='multiple_relay_at_open_time',task=task,t=str(t)))
                assignment[task]=rid
        for task,rid in points.get(t,[]):
            if task in assignment and assignment[task]!=rid:errors.append(dict(kind='boundary_conflict',task=task,t=str(t)))
            assignment[task]=rid
        by=defaultdict(list)
        for task,rid in assignment.items():
            if rid:by[rid].append(task)
        for rid,tasks in by.items():
            if rid not in maxima or len(tasks)>maxima[rid]['max_concurrent']:
                maxima[rid]=dict(max_concurrent=len(tasks),witness_time_decimal=str(t),witness_type=kind,tasks=sorted(tasks))
        return dict(sorted((k,sorted(v)) for k,v in by.items()))
    for t in times:evaluate(t,'exact listed boundary')
    for a,b in zip(times,times[1:]):evaluate((a+b)/2,'interior of interval between exhaustive state boundaries')
    at817=evaluate(D(817),'specified 817 s check')
    return dict(passed=not errors,errors=errors,state_source=str(path),state_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                relay_maxima=dict(sorted(maxima.items())),at_817_s=at817,distinct_event_times=len(times),
                assumption='No imposed relay concurrent-session limit; this counts actual nominal relay states, not all standby bindings.',
                proof='All state changes are in the independently checked analytic partition. Between consecutive distinct boundaries every task provider is constant; all boundary instants are checked separately.')



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
