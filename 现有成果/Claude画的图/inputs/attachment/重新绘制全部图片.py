"""在本文件所在目录运行；只重绘PNG/SVG，不求解，不生成PDF。"""
from pathlib import Path
import subprocess,sys
B=Path(__file__).resolve().parent
SKIP={'common','figstyle','flowkit','render_flows'}
for group in ['src','new','fusion']:
 for p in sorted((B/'figures'/group).glob('*.py')):
  if p.stem not in SKIP:
   subprocess.run([sys.executable,str(p)],check=True,cwd=p.parent)
print('28幅图已重新绘制，输出在各图源目录或其output子目录。')
