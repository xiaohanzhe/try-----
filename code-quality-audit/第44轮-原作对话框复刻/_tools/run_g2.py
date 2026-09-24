# -*- coding: utf-8 -*-
"""跑 G2 全量回归并把输出落盘到仓库内（避免 Bash/PowerShell 管道不稳）。"""
import io
import os
import subprocess
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PY = r'C:\Python311\python.exe'
OUT = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out', 'G2全量输出.txt')

r = subprocess.run([PY, os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')],
                   cwd=ROOT, capture_output=True)
txt = (r.stdout or b'').decode('utf-8', 'replace') + \
      (r.stderr or b'').decode('utf-8', 'replace')
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(txt)
lines = txt.split('\n')
print('rc=%d  lines=%d' % (r.returncode, len(lines)))
print('---- tail 24 ----')
for l in lines[-24:]:
    print(l)
