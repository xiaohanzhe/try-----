# -*- coding: utf-8 -*-
"""第48轮 · 跑 probe_strings48.csx（指定章）

用法: C:\\Python311\\python.exe run_strings48.py chapter1_windows
"""
import io
import os
import shutil
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
EXE = r'E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe'
CWD = r'E:\Download\UTMT_CLI_v0.9.2.0'
DRW = r'E:\Download\_tmp\drw'
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'probe_strings48.csx')

ch = sys.argv[1] if len(sys.argv) > 1 else 'chapter1_windows'
W = os.path.join(DRW, ch)
if not os.path.isfile(os.path.join(W, 'data.win')):
    print('缺少 data.win: %s' % W)
    sys.exit(1)

sdir = os.path.join(W, 'scripts')
if not os.path.isdir(sdir):
    os.makedirs(sdir)
dst = os.path.join(sdir, 'probe_strings48.csx')
shutil.copyfile(SRC, dst)

t0 = time.time()
p = subprocess.Popen([EXE, 'load', os.path.join(W, 'data.win'), '-s', dst], cwd=CWD,
                     stdin=subprocess.DEVNULL,
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
out = p.stdout.read().decode('utf-8', 'replace')
p.wait()
print('[%s] rc=%d  %.1fs' % (ch, p.returncode, time.time() - t0))
print(out[-800:])
fp = os.path.join(W, 'probe_strings48.txt')
if os.path.isfile(fp):
    txt = io.open(fp, encoding='utf-8', errors='replace').read()
    print(txt[:3000])
