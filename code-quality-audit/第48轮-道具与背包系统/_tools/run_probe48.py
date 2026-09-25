# -*- coding: utf-8 -*-
"""第48轮 · 跑 probe_items48.csx（指定章；只 load + -s，不落盘 data.win）

用法: C:\\Python311\\python.exe run_probe48.py chapter1_windows
"""
import hashlib
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
SRC = os.path.join(HERE, 'probe_items48.csx')

ch = sys.argv[1] if len(sys.argv) > 1 else 'chapter1_windows'
W = os.path.join(DRW, ch)


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


wm = os.path.join(W, 'data.win')
if not os.path.isfile(wm):
    print('缺少 data.win: %s' % wm)
    sys.exit(1)
before = sha(wm)
sdir = os.path.join(W, 'scripts')
if not os.path.isdir(sdir):
    os.makedirs(sdir)
dst = os.path.join(sdir, 'probe_items48.csx')
shutil.copyfile(SRC, dst)

t = time.time()
p = subprocess.Popen([EXE, 'load', wm, '-s', dst], cwd=CWD,
                     stdin=subprocess.DEVNULL,
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
out = p.stdout.read().decode('utf-8', 'replace')
p.wait()
print('[%s] rc=%d  %.1fs' % (ch, p.returncode, time.time() - t))
print(out[-2000:])
print('data.win 未改动: %s' % (before == sha(wm)))
fp = os.path.join(W, 'probe_items48.json')
print('  probe_items48.json  %s' % (('%d B' % os.path.getsize(fp)) if os.path.isfile(fp) else '(缺)'))
