import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

"""Recompute both fixed Q1 objective orders from original inputs."""
from dcore import Model, dump, ROOT, csvwrite
from q1_engine import q1_solve
import argparse, json
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.parse_args()
    model=Model()
    for priority,name in [('sorties_energy','q1'),('energy_sorties','q1_energy_first')]:
        result=q1_solve(model,priority=priority)
        dump(ROOT/'output/reproduced'/f'{name}.json',result)
        print(name,json.dumps(result['metrics'],ensure_ascii=False),flush=True)
    csvwrite(ROOT/'output/reproduced/q1_payloads.csv',[dict(type=g,site=s,**model.max_payload(g,s)) for g in model.types for s in model.nodes if s!='O01'])
if __name__=='__main__':main()
