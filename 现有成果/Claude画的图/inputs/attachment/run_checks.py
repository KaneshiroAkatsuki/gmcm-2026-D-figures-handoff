"""在独立副本中核验当前结果；不搜索运输方案，不改results。"""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
sys.dont_write_bytecode=True
B=Path(__file__).resolve().parent
out=B/'output/reproduced'
if out.exists():raise FileExistsError('output/reproduced已存在，请在新的目录副本中运行')
out.mkdir(parents=True)
names=['q1','q1_energy_first','q2','q3','q4','q4_no_copy_sensitivity']
source_hash={n:hashlib.sha256((B/'results'/f'{n}.json').read_bytes()).hexdigest() for n in names}
for n in names:shutil.copy2(B/'results'/f'{n}.json',out/f'{n}.json')
for script in ['write_nominal_view.py','check_current_results.py','check_q4.py']:
 subprocess.run([sys.executable,'-B',str(B/'src'/script)],cwd=B,check=True)
assert all(hashlib.sha256((B/'results'/f'{n}.json').read_bytes()).hexdigest()==h for n,h in source_hash.items())
print(json.dumps({'passed':True,'source_results_unchanged':True}))
