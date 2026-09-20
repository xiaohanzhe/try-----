# -*- coding: utf-8 -*-
"""W1-3 e2e 运行器：跑 verify_w1_3_e2e.py 并抽取关键行（自写 UTF-8，避免 shell 编码损伤）。"""
import io
import os
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
iso = tempfile.mkdtemp(prefix='w13_iso_')
env = dict(os.environ)
env['PYTHONIOENCODING'] = 'utf-8'
env['PYTHONUTF8'] = '1'
env['QT_QPA_PLATFORM'] = 'offscreen'
env['RALSEI_MEMORY_DIR'] = os.path.join(iso, 'RalseiMemory')

script = os.path.join(ROOT, 'code-quality-audit', '架构改造-H4H5', sys.argv[1])
p = subprocess.run([r'C:\Python311\python.exe', script],
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                   env=env, cwd=os.getcwd())
t = p.stdout.decode('utf-8', 'replace')

tag = sys.argv[2] if len(sys.argv) > 2 else 'run'
outdir = r'E:\Download\_tmp'
io.open(os.path.join(outdir, 'w13_%s_full.txt' % tag), 'w', encoding='utf-8', newline='\n').write(t)

keep = []
for ln in t.split('\n'):
    if ('[PASS]' in ln or '[FAIL]' in ln or ln.startswith('合计')
            or 'Error' in ln or 'Traceback' in ln or ln.startswith('  File "')
            or ln.startswith('=') or ln.startswith('---')):
        keep.append(ln)
io.open(os.path.join(outdir, 'w13_%s_clean.txt' % tag), 'w', encoding='utf-8', newline='\n').write('\n'.join(keep))
print('exit=%d pass=%d fail=%d' % (p.returncode, t.count('[PASS]'), t.count('[FAIL]')))
