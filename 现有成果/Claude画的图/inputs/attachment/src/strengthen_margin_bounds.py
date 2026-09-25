import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from independent_check import read_originals
from check_q3_plan_v0031 import IndependentLinks,PROJECT


def run(plan,report):
    data=json.loads(plan.read_text(encoding='utf-8'))
    audit=json.loads(report.read_text(encoding='utf-8'))
    assert hashlib.sha256(plan.read_bytes()).hexdigest()==audit['source_sha256']
    assert audit['complete_Q3_independent_pass']
    cfg=audit['communication']['acceptance'];original=PROJECT/'data/original'
    nodes,*_=read_originals(original)
    links=IndependentLinks(original,nodes,cfg['delta_g_db'],cfg['clearance_m'])
    tasks={x['id']:x for x in data['tasks']};relays={x['id']:x for x in data['relays']}
    records=[];tested=0;strengthened=0
    for cert in audit['communication']['certificates']:
        proof=cert['proof'];margin=proof['nominal_budget_margin_lower_db'];new=margin
        extra={}
        if margin<.1 and proof['method']=='convex_distance_endpoints_with_full_10dB_obstruction':
            e=tasks[cert['task']]['events'][cert['event']]
            def pos(t):
                u=(t-e['start'])/(e['end']-e['start']) if e['end']!=e['start'] else 0
                return (np.array(e['p0'])+(np.array(e['p1'])-e['p0'])*u).tolist()
            p0=pos(cert['start']);p1=pos(cert['end'])
            anchor=links.gateway if cert['mode']=='direct' else relays[cert['relay']]['position']
            tested+=1;los=links.los(anchor,p0,p1)
            if los['certified']:
                new=margin+links.p['obstruction'];strengthened+=1
                extra={'stronger_method':'all_time_triangle_LOS_and_endpoint_distance','los':los}
        records.append({k:cert[k] for k in ['task','event','start','end','point','mode','relay']}|
                       dict(original_nominal_bound_db=margin,verified_nominal_bound_db=new,**extra))
    return dict(source=str(plan),source_sha256=audit['source_sha256'],independent_report=str(report),
                acceptance=cfg,interval_count=audit['communication']['interval_count'],
                boundary_count=audit['communication']['boundary_point_count'],
                candidates_tested=tested,bounds_strengthened=strengthened,
                minimum_certified_nominal_margin_db=min(x['verified_nominal_bound_db'] for x in records),
                minimum_gate_surplus_db=min(x['verified_nominal_bound_db'] for x in records)-cfg['delta_g_db'],
                minimum_cases=[x for x in records if x['verified_nominal_bound_db']==min(r['verified_nominal_bound_db'] for r in records)],
                records=records)



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reusable numerical module. See README_reproduction.md for stage commands.")
    parser.parse_args()
    print("Module import check passed.")
