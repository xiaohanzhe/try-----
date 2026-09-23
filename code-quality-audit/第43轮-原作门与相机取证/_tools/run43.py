# -*- coding: utf-8 -*-
"""第43轮 · 跑 view43.csx / func43.csx（指定章；只 load + -s，不落盘 data.win）

用法: python run43.py <脚本名不带.csx> <chapter1_windows>
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
TMP = r'E:\Download\_tmp'

name = sys.argv[1] if len(sys.argv) > 1 else 'view43'
ch = sys.argv[2] if len(sys.argv) > 2 else 'chapter1_windows'
W = os.path.join(DRW, ch)
SRC = os.path.join(TMP, name + '.csx')


def sha(p):
    hh = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            hh.update(b)
    return hh.hexdigest()


if not os.path.isfile(SRC):
    print('缺少脚本: %s' % SRC)
    sys.exit(1)
wm = os.path.join(W, 'data.win')
if not os.path.isfile(wm):
    print('缺少 data.win: %s' % wm)
    sys.exit(1)
before = sha(wm)
sdir = os.path.join(W, 'scripts')
os.makedirs(sdir, exist_ok=True)
dst = os.path.join(sdir, name + '.csx')
shutil.copyfile(SRC, dst)

t = time.time()
p = subprocess.Popen([EXE, 'load', wm, '-s', dst], cwd=CWD,
                     stdin=subprocess.DEVNULL,
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
out = p.stdout.read().decode('utf-8', 'replace')
p.wait()
print('[%s/%s] rc=%d  %.1fs' % (ch, name, p.returncode, time.time() - t))
print(out[-3000:])
print('data.win 未改动: %s' % (before == sha(wm)))
for ext in ('.txt', '.json'):
    fp = os.path.join(W, name + ext)
    print('  %-16s %s' % (name + ext,
                          ('%d B' % os.path.getsize(fp)) if os.path.isfile(fp) else '(缺)'))
