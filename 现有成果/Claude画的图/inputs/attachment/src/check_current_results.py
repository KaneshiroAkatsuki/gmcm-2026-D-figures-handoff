import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

"""Independent raw-data check of Q1/Q2/Q3, full-time communication, nominal endpoints and concurrency."""
from pathlib import Path
from decimal import localcontext
import argparse,hashlib,json
from independent_check import audit,read_originals
from check_formal_outputs import check_solution
from check_q3_plan_v0031 import resource_check,communication_check
from check_nominal_states import run as check_nominal
from strengthen_margin_bounds import run as strengthen
from exact_nominal_relay_concurrency import run as concurrency
from check_experiment import strict_contract, reported_metrics_check
ROOT=Path(__file__).resolve().parents[1]
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.parse_args()
    original=ROOT/'data/original';out=ROOT/'output/reproduced/checks';out.mkdir(parents=True,exist_ok=True)
    common=audit(original,out);nodes,models,entities,boxes=read_originals(original)
    results={}
    for name,kind in [('q1','Q1'),('q1_energy_first','Q1'),('q2','Q2'),('q3','Q2')]:
        results[name]=check_solution(read(ROOT/f'output/reproduced/{name}.json'),kind,nodes,models,entities,boxes,common)
        assert results[name]['passed'],results[name]['errors']
    plan=ROOT/'output/reproduced/q3.json';q=read(plan)
    contract=strict_contract(q);assert contract['passed'],contract['errors']
    relay=resource_check(q,original,nodes)
    totals=reported_metrics_check(q,results['q3'],relay);assert totals['passed'],totals['errors']
    comm=communication_check(q,original,nodes,.01,1.,False)
    passed=results['q3']['passed'] and relay['passed'] and comm['all_selected_links_independently_certified'] and comm['direct_priority_independently_certified']
    report=dict(source='output/reproduced/q3.json',source_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),transport=results['q3'],relay=relay,communication=comm,resources_passed=results['q3']['passed'] and relay['passed'],complete_Q3_independent_pass=passed)
    write(out/'q3_independent.json',report);assert passed
    with localcontext() as context:
        context.prec=100;nominal=check_nominal(plan,ROOT/'output/reproduced/nominal_states.json');con=concurrency(ROOT/'output/reproduced/nominal_states.json')
    assert nominal['passed'] and con['passed']
    bounds=strengthen(plan,out/'q3_independent.json')
    assert bounds['minimum_certified_nominal_margin_db']>=.01
    for name,value in [('transport_checks',results),('nominal_check',nominal),('concurrency',con),('strengthened_bounds',bounds),('strict_contract',contract),('reported_metrics',totals)]:write(out/f'{name}.json',value)
    summary=dict(passed=True,transport={k:v['passed'] for k,v in results.items()},robust_interval_count=comm['interval_count'],robust_boundary_count=comm['boundary_point_count'],nominal_interval_count=nominal['interval_count'],nominal_boundary_count=nominal['boundary_count'],minimum_strengthened_margin_db=bounds['minimum_certified_nominal_margin_db'],concurrency={k:v['max_concurrent'] for k,v in con['relay_maxima'].items()})
    write(out/'check_summary.json',summary);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
