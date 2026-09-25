"""Report every numeric difference after a separate raw-data replay."""
import sys
sys.dont_write_bytecode=True
for s in (sys.stdout,sys.stderr):
    if hasattr(s,'reconfigure'):s.reconfigure(encoding='utf-8')
import argparse,hashlib,json,re,time
from decimal import Decimal,localcontext
from pathlib import Path
from fixed_replay_core import save

NUMERIC=re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')

def compare(reference,replayed):
    differences=[];structure=[];counts=dict(numeric_values=0,exact_numeric_differences=0,string_numeric_values=0,string_numeric_differences=0,non_numeric_values=0)
    def walk(a,b,path):
        if isinstance(a,dict) and isinstance(b,dict):
            for k in b:
                if k not in a:structure.append(dict(path=path+'.'+k,reason='Missing reference field'))
                else:walk(a[k],b[k],path+'.'+k)
        elif isinstance(a,list) and isinstance(b,list):
            if len(a)!=len(b):structure.append(dict(path=path,reason='List length differs',reference=len(a),replayed=len(b)))
            for i,(x,y) in enumerate(zip(a,b)):walk(x,y,f'{path}[{i}]')
        elif isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
            counts['numeric_values']+=1
            if a!=b:
                counts['exact_numeric_differences']+=1;delta=abs(Decimal(str(a))-Decimal(str(b)))
                differences.append(dict(path=path,reference=a,replayed=b,absolute_difference=str(delta),within_comparison_tolerance=delta<=Decimal('1e-8'),kind='number'))
        elif isinstance(a,str) and isinstance(b,str) and NUMERIC.fullmatch(a) and NUMERIC.fullmatch(b):
            counts['string_numeric_values']+=1
            if Decimal(a)!=Decimal(b):
                counts['string_numeric_differences']+=1;delta=abs(Decimal(a)-Decimal(b))
                differences.append(dict(path=path,reference=a,replayed=b,absolute_difference=str(delta),within_comparison_tolerance=delta<=Decimal('1e-70'),kind='numeric_string'))
        else:
            counts['non_numeric_values']+=1
            if a!=b:structure.append(dict(path=path,reason='Non-numeric value differs',reference=a,replayed=b))
    with localcontext() as context:
        context.prec=120
        for field in ('tasks','relays'):
            if field not in replayed:continue
            originals={r['id']:r for r in reference[field]}
            if set(originals)!={r['id'] for r in replayed[field]}:structure.append(dict(path=field,reason='IDs differ'))
            for row in replayed[field]:
                if row['id'] in originals:walk(originals[row['id']],row,field+'.'+row['id'])
        for field in ('metrics','transport_metrics','joint_metrics'):
            if field in replayed:
                if field not in reference:structure.append(dict(path=field,reason='Reference metric block missing'))
                else:walk(reference[field],replayed[field],field)
        if 'communication' in replayed:
            for field in ('intervals','boundary_points'):
                a=reference['communication'][field];b=replayed['communication'][field]
                def clean(rows):return [{k:v for k,v in r.items() if k not in ('interval',)} for r in rows]
                walk(clean(a),clean(b),'communication.'+field)
            walk(reference['communication']['backhaul_certificates'],replayed['communication']['backhaul_certificates'],'communication.backhaul_certificates')
            walk(reference['communication']['min_certified_margin_db'],replayed['communication']['min_certified_margin_db'],'communication.min_certified_margin_db')
        if 'nominal_communication' in replayed:
            walk(reference['nominal_communication'],replayed['nominal_communication'],'nominal_communication')
    return dict(comparison_scope='Every reconstructed transport/relay physical field and aggregate metric; all regenerated robust rows/backhaul proofs; all nominal state fields. Old producer metadata and fields not reconstructed are excluded.',comparison_only_absolute_tolerance='JSON numeric fields: 1e-8; analytic numeric strings: 1e-70. These only label recomputation differences, never accept resource, communication, or clearance violations.',counts=counts,exactly_equal=not differences and not structure,all_numeric_within_comparison_tolerance=all(d['within_comparison_tolerance'] for d in differences),structure_equal=not structure,max_absolute_difference=max((Decimal(d['absolute_difference']) for d in differences),default=Decimal(0)).to_eng_string(),differences=differences,structural_differences=structure)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--replayed',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    started=time.perf_counter();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before=[sha(a.reference),sha(a.replayed)]
    r=compare(json.loads(a.reference.read_text(encoding='utf-8')),json.loads(a.replayed.read_text(encoding='utf-8')))
    r.update(reference_sha256=before[0],replayed_sha256=before[1],input_hashes_unchanged=before==[sha(a.reference),sha(a.replayed)],seconds=time.perf_counter()-started)
    save(a.output,r);print(json.dumps({k:v for k,v in r.items() if k not in ('differences','structural_differences')},ensure_ascii=False))
    if not r['all_numeric_within_comparison_tolerance'] or not r['structure_equal']:raise SystemExit(1)
if __name__=='__main__':main()
