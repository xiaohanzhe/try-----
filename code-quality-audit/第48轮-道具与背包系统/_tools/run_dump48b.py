# -*- coding: utf-8 -*-
"""第48轮 · 跑 dump_items48b.csx（补采版）：只换输出目录，绕开 tmp 覆盖被拒故障。

用法: C:\\Python311\\python.exe run_dump48b.py chapter1_windows
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
SRC = os.path.join(HERE, 'dump_items48b.csx')


def _need_copy(dst):
    if not os.path.isfile(dst):
        return True
    try:
        with io.open(dst, 'rb') as a, io.open(SRC, 'rb') as b:
            return a.read() != b.read()
    except OSError:
        return True


for ch in (sys.argv[1:] or ['chapter1_windows']):
    W = os.path.join(DRW, ch)
    if not os.path.isfile(os.path.join(W, 'data.win')):
        print('缺少 data.win: %s' % W)
        continue
    sdir = os.path.join(W, 'scripts')
    if not os.path.isdir(sdir):
        os.makedirs(sdir)
    dst = os.path.join(sdir, 'dump_items48b.csx')
    if _need_copy(dst):
        try:
            shutil.copyfile(SRC, dst)
        except PermissionError:
            print('   ⚠️ csx 复制被拒（已知间歇故障）；沿用旧副本继续')
    t0 = time.time()
    p = subprocess.Popen([EXE, 'load', os.path.join(W, 'data.win'), '-s', dst], cwd=CWD,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.read().decode('utf-8', 'replace')
    p.wait()
    print('[%s] rc=%d  %.1fs' % (ch, p.returncode, time.time() - t0))
    print(out[-800:])
    lg = os.path.join(W, 'dump_log48b.txt')
    if os.path.isfile(lg):
        lines = io.open(lg, encoding='utf-8').read().splitlines()
        miss = [l for l in lines if l.startswith('MISS')]
        bad = [l for l in lines if l.startswith('OK') and 'DECOMPILE' in l]
        print('  OK %d / MISS %d / 失败 %d' % (len(lines) - len(miss), len(miss), len(bad)))
        for l in miss[:20]:
            print('    ', l)
