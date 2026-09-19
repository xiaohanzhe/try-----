# -*- coding: utf-8 -*-
"""跑 check_probe_fidelity.py 并把输出写成 UTF-8 文件（Python 自写，不经 PowerShell）。"""
import io
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r'C:\Python311\python.exe'
OUT = os.path.join(HERE, '_evidence', 'probe_fidelity_2026-09-20.txt')

p = subprocess.run([PY, os.path.join(HERE, 'check_probe_fidelity.py')],
                   capture_output=True, text=True, encoding='utf-8',
                   errors='replace', cwd=HERE, timeout=180)
body = (p.stdout or '') + (p.stderr or '')
os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, 'w', encoding='utf-8').write(body)
print('rc=%d' % p.returncode)
print('WROTE %s' % OUT)
