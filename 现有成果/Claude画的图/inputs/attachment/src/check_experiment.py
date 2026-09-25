"""Validate one immutable Q3 candidate; never run a search or alter the plan."""
from pathlib import Path
from decimal import localcontext
from datetime import datetime
import argparse, hashlib, json, math, os, re, sys, time, traceback

sys.dont_write_bytecode = True
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT.parent
VALIDATION = ROOT/'output/validation'
DELTA_DB = 0.01
CLEARANCE_M = 1.0

def within(path, parent):
    try:
        Path(path).resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def reported_metrics_check(plan, transport, relay):
    """Reject stale/fabricated summaries even when detailed tasks are feasible."""
    from check_formal_outputs import Findings
    f=Findings();tm=transport['metrics']
    f.require(transport.get('passed') and relay.get('passed'),'reported_metrics','Physical checks must pass before comparing summaries')
    expected_transport=dict(sorties=tm['sorties'],energy=tm['total_energy_kwh'],
        cumulative_time=tm['cumulative_operation_s'],makespan=tm['makespan_s'],
        delivered=tm['box_count'],hard_violations=[],
        weighted_soft_tardiness=tm['weighted_other_tardiness_s'],soft_late_count=len(tm['late_other_boxes']))
    expected_joint=dict(makespan=max(tm['makespan_s'],relay['last_return_s']),
        transport_energy=tm['total_energy_kwh'],relay_energy=relay['energy_kwh'],
        total_energy=tm['total_energy_kwh']+relay['energy_kwh'],
        transport_sorties=len(plan['tasks']),relay_sorties=len(plan['relays']),
        total_sorties=len(plan['tasks'])+len(plan['relays']))
    for name,expected,mandatory in [('metrics',expected_transport,True),('transport_metrics',expected_transport,False),('joint_metrics',expected_joint,True)]:
        if name not in plan and not mandatory:continue
        values=plan.get(name)
        f.require(isinstance(values,dict),name,'Missing metric object')
        if not isinstance(values,dict):continue
        f.require(set(values)==set(expected),name,'Metric keys must be complete and independently supported')
        for key,target in expected.items():
            if isinstance(target,list):f.require(values.get(key)==target,name+'.'+key,'Hard-violation list disagrees with independent physical result')
            elif key in {'sorties','delivered','soft_late_count','transport_sorties','relay_sorties','total_sorties'}:
                f.require(type(values.get(key)) in (int,float) and values[key]==target,name+'.'+key,'Count disagrees with independent result')
            else:f.close(values.get(key),target,name+'.'+key)
    return dict(passed=not f.errors,errors=f.errors,comparison_count=f.comparisons,
                independent_transport_metrics=expected_transport,independent_joint_metrics=expected_joint)

def write(path, value):
    assert within(path, VALIDATION), 'Validation output escaped dedicated directory'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def strict_contract(plan):
    """No positive time hole is excused as numerical roundoff in certificate partition."""
    errors=[]
    def bad(where, reason): errors.append(dict(where=where, message=reason))
    def finite(obj, where='$'):
        if isinstance(obj, float) and not math.isfinite(obj):bad(where, 'Nonfinite numeric value')
        elif isinstance(obj, dict):
            for k,v in obj.items():finite(v, where+'.'+k)
        elif isinstance(obj, list):
            for k,v in enumerate(obj):finite(v, f'{where}[{k}]')
    finite(plan)
    if not isinstance(plan.get('tasks'),list) or not plan.get('tasks'):bad('tasks','Missing nonempty task list')
    if not isinstance(plan.get('relays'),list):bad('relays','Missing relay list')
    for name in ['communication','nominal_communication']:
        if not isinstance(plan.get(name),dict):bad(name,'Missing full certificate/state object; build it in candidate output before validation')
    if errors:return dict(passed=False,errors=errors)
    comm=plan['communication'];byevent={};bypoints={}
    for row in comm.get('intervals',[]):byevent.setdefault((row.get('task'),row.get('event')),[]).append(row)
    for row in comm.get('boundary_points',[]):bypoints.setdefault((row.get('task'),row.get('event')),[]).append(row)
    expected=set()
    for t in plan['tasks']:
        for ei,event in enumerate(t.get('events',[])):
            if 'p0' not in event:continue
            key=(t.get('id'),ei);expected.add(key);where=f'{key[0]}.event{ei}'
            a,b=event['start'],event['end'];rows=sorted(byevent.get(key,[]),key=lambda r:(r['start'],r['end']))
            points={r['time'] for r in bypoints.get(key,[])}
            if not rows:bad(where,'Missing robust interval coverage');continue
            if rows[0]['start']!=a or rows[-1]['end']!=b:bad(where,'Certificate endpoints do not exactly match stored event endpoints')
            for r in rows:
                if not a<=r['start']<=r['end']<=b:bad(where,'Certificate interval leaves event range')
                if r['start'] not in points or r['end'] not in points:bad(where,'Missing exact listed boundary for robust interval')
            for prev,next_ in zip(rows,rows[1:]):
                if prev['end']!=next_['start']:bad(where,f"Strict gap/overlap: {prev['end']!r} versus {next_['start']!r}")
            if any(not a<=p<=b for p in points):bad(where,'Robust boundary outside event range')
    if not expected:bad('tasks.events','No physical communication phases')
    if set(byevent)!=expected or set(bypoints)!=expected:bad('communication','Unexpected or missing task/event keys')
    for field,minimum in [('delta_g_db',DELTA_DB),('clearance_m',CLEARANCE_M)]:
        if field in comm and comm[field]<minimum:bad('communication.'+field,'Producer metadata uses lower robustness gate')
    if comm.get('budget_roundoff_tolerance_db',0)!=0:bad('communication.budget_roundoff_tolerance_db','Negative-budget allowance is prohibited')
    return dict(passed=not errors,errors=errors,physical_event_count=len(expected),strict_time_partition=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    args=parser.parse_args()
    plan_path=args.plan.resolve()
    if not within(plan_path,LAB):
        parser.error('--plan must be inside the independent method lab')
    raw=plan_path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    slug=re.sub(r'[^A-Za-z0-9_.-]+','_',plan_path.stem)
    run_dir=VALIDATION/f"{slug}_{sha[:12]}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    run_dir.mkdir(parents=True)
    started=time.perf_counter();report=dict(plan=str(plan_path),source_sha256=sha,validation_directory=str(run_dir),acceptance=dict(delta_g_db=DELTA_DB,clearance_m=CLEARANCE_M,budget_negative_tolerance_db=0,concurrent_session_cap=None),stages={},stage_seconds={},exceptions=[],no_search_performed=True)

    # Runtime write guard applies to dependencies too. Imports may read installed libraries.
    def write_guard(event,args_):
        targets=[]
        if event=='open' and args_:
            path=args_[0];mode=args_[1] if len(args_)>1 else None;flags=args_[2] if len(args_)>2 else 0
            writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_APPEND|os.O_CREAT|os.O_TRUNC)))
            if writing and isinstance(path,(str,bytes,os.PathLike)):targets=[path]
        elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod','os.truncate','os.utime') and args_:targets=[args_[0]]
        elif event in ('os.rename','os.replace','os.link','os.symlink') and len(args_)>=2:targets=list(args_[:2])
        for target in targets:
            if isinstance(target,(str,bytes,os.PathLike)) and not within(os.fsdecode(target),run_dir):
                raise PermissionError(f'Validation write outside run directory blocked: {target!r}')
    sys.addaudithook(write_guard)

    def stage(name,fn):
        t=time.perf_counter()
        try:
            value=fn();report['stages'][name]=value;write(run_dir/(name+'.json'),value)
            return value
        except Exception as exc:
            value=dict(passed=False,exception_type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
            report['stages'][name]=value;report['exceptions'].append(dict(stage=name,**value));write(run_dir/(name+'.json'),value)
            return value
        finally:report['stage_seconds'][name]=time.perf_counter()-t

    try:
        plan=json.loads(raw.decode('utf-8'))
        contract=stage('contract',lambda:strict_contract(plan))
        if contract['passed']:
            from independent_check import audit, read_originals
            from check_formal_outputs import check_solution, Findings
            from check_q3_plan_v0031 import resource_check, communication_check
            from check_nominal_states import run as nominal_check
            from exact_nominal_relay_concurrency import run as concurrency_check
            from strengthen_margin_bounds import run as strengthen
            original=ROOT/'data/original'
            common=stage('common_geometry',lambda:audit(original,run_dir/'common'))
            if 'legs' in common:
                nodes,models,entities,boxes=read_originals(original)
                transport=stage('transport',lambda:check_solution(plan,'Q2',nodes,models,entities,boxes,common))
                relay=stage('relay_resources',lambda:resource_check(plan,original,nodes))
                totals=stage('joint_metrics',lambda:reported_metrics_check(plan,transport,relay)) if transport.get('passed') and relay.get('passed') else dict(passed=False)
                if transport.get('passed') and relay.get('passed') and totals.get('passed'):
                    comm=stage('robust_communication',lambda:communication_check(plan,original,nodes,DELTA_DB,CLEARANCE_M,False))
                    robust_pass=bool(comm.get('all_selected_links_independently_certified') and comm.get('direct_priority_independently_certified'))
                    physical_report=dict(source=str(plan_path),source_sha256=sha,transport=transport,relay=relay,communication=comm,resources_passed=True,complete_Q3_independent_pass=robust_pass)
                    write(run_dir/'q3_independent.json',physical_report)
                    nominal_path=run_dir/'nominal_states.json';write(nominal_path,plan['nominal_communication'])
                    with localcontext() as context:
                        context.prec=100
                        nominal=stage('nominal_states_check',lambda:nominal_check(plan_path,nominal_path))
                        concurrent=stage('nominal_concurrency',lambda:concurrency_check(nominal_path))
                    if robust_pass:
                        bounds=stage('strengthened_bounds',lambda:strengthen(plan_path,run_dir/'q3_independent.json'))
                    else:bounds=dict(passed=False,reason='Robust independent gate failed; no margin strengthening claim')
                    report['passed']=bool(robust_pass and nominal.get('passed') and concurrent.get('passed') and bounds.get('minimum_certified_nominal_margin_db',-math.inf)>=DELTA_DB and totals.get('passed'))
                else:report['skipped']='Continuous/nominal checks skipped because physical transport, relay schedule, or reported metrics failed'
            else:report['skipped']='Physical checks skipped because independent original geometry failed'
        else:report['skipped']='Plan contract rejected before expensive geometry checks'
    except Exception as exc:
        report['exceptions'].append(dict(stage='orchestrator',exception_type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    report['passed']=bool(report.get('passed',False))
    report['input_hash_unchanged']=digest(plan_path)==sha
    report['passed']=report['passed'] and report['input_hash_unchanged'] and not report['exceptions']
    report['elapsed_seconds']=time.perf_counter()-started
    report['exit_code']=0 if report['passed'] else 1
    report['command']=['python',str(Path(__file__).resolve()),'--plan',str(plan_path)]
    report['validation_module_sha256']={p.name:digest(p) for p in Path(__file__).parent.glob('*.py') if p.name in ['check_experiment.py','independent_check.py','check_formal_outputs.py','check_q3_plan_v0031.py','check_nominal_states.py','strengthen_margin_bounds.py','exact_nominal_relay_concurrency.py','independent_triangle_los.py','independent_rational_shadow.py']}
    write(run_dir/'validation_report.json',report)
    print(json.dumps(dict(passed=report['passed'],input_hash_unchanged=report['input_hash_unchanged'],report=str(run_dir/'validation_report.json'),elapsed_seconds=report['elapsed_seconds'],exit_code=report['exit_code']),ensure_ascii=False))
    return report['exit_code']

if __name__=='__main__':
    raise SystemExit(main())
