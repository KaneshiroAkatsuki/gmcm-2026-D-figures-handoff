import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

"""Independent exhaustive Q4 and resource colouring check, from raw resources and reproduced Q3."""
import argparse,json
from pathlib import Path
import independent_partition as audit
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.parse_args()
    assert audit.selftest()['passed']
    q=json.loads((ROOT/'output/reproduced/q3.json').read_text(encoding='utf-8'))
    raw=audit.raw_inputs();context=audit.context(q,raw);demand,work=audit.precompute(context)
    result={}
    for name,key,filename in [('copy','copy_components','q4.json'),('no_copy','no_copy_components','q4_no_copy_sensitivity.json')]:
        own=audit.enumerate_rule(context,raw,demand,work,context[key])
        formal=json.loads((ROOT/'output/reproduced'/filename).read_text(encoding='utf-8'))
        comparison=audit.compare(formal,own);assert comparison['passed']
        result[name]=dict(passed=True,comparison=comparison,enumeration=own)
    path=ROOT/'output/reproduced/checks/q4_independent.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v['passed'] for k,v in result.items()}))
if __name__=='__main__':main()
