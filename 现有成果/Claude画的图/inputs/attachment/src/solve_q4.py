import sys
sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

"""Replay exhaustive Q4 enumeration under both fixed relay-copy conventions."""
from pathlib import Path
from collections import defaultdict
import argparse,json,hashlib
from dcore import Model,dump,ROOT
import partition_frozen as engine
def no_copy_components(model,q):
    sites=sorted(k for k in model.nodes if k!='O01');parent={k:k for k in sites}
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    def join(seq):
        if seq:
            for x in seq:parent[find(x)]=find(seq[0])
    tasks={t['id']:t for t in q['tasks']}
    for t in tasks.values():join(t['order'])
    serving=defaultdict(set)
    for row in q['communication']['intervals']+q['communication']['boundary_points']:
        if row.get('relay'):serving[row['relay']].update(tasks[row['task']]['order'])
    for members in serving.values():join(sorted(members))
    groups=defaultdict(list)
    for site in sites:groups[find(site)].append(site)
    return sorted(groups.values(),key=lambda x:x[0])
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.parse_args()
    path=ROOT/'output/reproduced/q3.json';q=json.loads(path.read_text(encoding='utf-8'));digest=hashlib.sha256(path.read_bytes()).hexdigest()
    report=json.loads((ROOT/'output/reproduced/checks/q3_independent.json').read_text(encoding='utf-8'))
    assert report['complete_Q3_independent_pass'] and report['source_sha256']==digest
    q['status']='independently_validated';q['frozen_sha256']=digest;model=Model()
    main=engine.solve(model,q);main['policy']='full_relay_task_copy_with_in_group_reassignment';dump(ROOT/'output/reproduced/q4.json',main)
    saved=engine._components
    try:
        engine._components=lambda mm,tasks:no_copy_components(mm,q)
        sensitivity=engine.solve(model,q)
    finally:engine._components=saved
    sensitivity['policy']='no_relay_task_copy_with_in_group_reassignment'
    sensitivity['assumptions']='固定全部物理任务、时刻及所有备用绑定；同运输任务和同中继任务涉及服务区均同组；不跨组复制中继任务；组内同型资源可重新分配'
    dump(ROOT/'output/reproduced/q4_no_copy_sensitivity.json',sensitivity)
    print(json.dumps({name:[dict(K=s['K'],groups=[g['sites'] for g in s['groups']],shortage=s['shortage'],cv=s['workload_cv']) for s in result['selected']] for name,result in [('copy',main),('no_copy',sensitivity)]},ensure_ascii=False))
if __name__=='__main__':main()
