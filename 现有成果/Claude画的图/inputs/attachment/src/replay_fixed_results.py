"""Recompute Q2/Q3 from raw inputs plus fixed decisions, never a prior result."""
import os,sys
sys.dont_write_bytecode=True
for s in (sys.stdout,sys.stderr):
    if hasattr(s,'reconfigure'):s.reconfigure(encoding='utf-8')
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
import argparse,hashlib,json,time
from pathlib import Path
from fixed_replay_core import ROOT,replay,save

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--decisions',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    started=time.perf_counter();raw=a.decisions.read_bytes();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();digest=hashlib.sha256(raw).hexdigest()
    original={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'data/original').rglob('*') if p.is_file()}
    if not original:raise RuntimeError('Original competition data are missing; place them in data/original as described in the README')
    decisions=json.loads(raw.decode('utf-8'));q=replay(decisions);save(a.output,q)
    assert sha(a.decisions)==digest and all(sha(ROOT/k)==v for k,v in original.items())
    report=dict(passed_self_check=True,decision_sha256=digest,result_sha256=sha(a.output),original_inputs_unchanged=True,original_input_hashes=original,seconds=time.perf_counter()-started,metrics=q['metrics'],joint_metrics=q.get('joint_metrics'),independent_validation='Required separately; this command performs raw recomputation and self-check only')
    report['raw_clock_reconstruction']={k:v for k,v in q['raw_clock_reconstruction'].items() if k!='differences'}
    if decisions['problem']=='Q3':report['nominal_precision']=dict(actual_working_precision_digits=decisions['nominal_working_precision_digits'],legacy_declared_precision_field=q['nominal_communication']['precision_decimal_digits'],meaning='Actual calculation precision is a fixed reproduction setting; the existing result metadata declaration is preserved for numerical comparison.')
    if 'communication' in q:report['communication']=dict(robust_intervals=len(q['communication']['intervals']),robust_boundaries=len(q['communication']['boundary_points']),nominal_intervals=len(q['nominal_communication']['intervals']),nominal_boundaries=len(q['nominal_communication']['boundary_points']),minimum_margin_db=q['communication']['min_certified_margin_db'])
    save(a.output.with_name(a.output.stem+'_run.json'),report)
    print(json.dumps({k:v for k,v in report.items() if k!='original_input_hashes'},ensure_ascii=False))
if __name__=='__main__':main()
