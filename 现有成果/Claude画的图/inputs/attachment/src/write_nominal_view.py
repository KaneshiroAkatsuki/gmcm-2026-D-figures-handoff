"""Export the recomputed nominal layer as a separate input view for its checker."""
import sys
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
import json
from pathlib import Path
def main():
    root=Path(__file__).resolve().parents[1]/'output/reproduced'
    q=json.loads((root/'q3.json').read_text(encoding='utf-8'))
    (root/'nominal_states.json').write_text(json.dumps(q['nominal_communication'],ensure_ascii=False,indent=2),encoding='utf-8')
    print('nominal_states.json')
if __name__=='__main__':main()
