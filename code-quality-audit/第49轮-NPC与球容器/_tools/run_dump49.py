# -*- coding: utf-8 -*-
"""第49轮 · 跑 dump49.csx：按章反编译 NPC / 跟随 / 球容器 相关 code。

用法: C:\\Python311\\python.exe run_dump49.py <chapterN_windows> [...]
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
SRC = os.path.join(HERE, 'dump49.csx')


def run_ch(ch):
    W = os.path.join(DRW, ch)
    dw = os.path.join(W, 'data.win')
    if not os.path.isfile(dw):
        print('[%s] 缺少 data.win %s' % (ch, W))
        return
    sdir = os.path.join(W, 'scripts')
    if not os.path.isdir(sdir):
        os.makedirs(sdir)
    dst = os.path.join(sdir, 'dump49.csx')
    need = True
    if os.path.isfile(dst):
        try:
            with io.open(dst, 'rb') as a, io.open(SRC, 'rb') as b:
                need = a.read() != b.read()
        except OSError:
            need = True
    if need:
        try:
            shutil.copyfile(SRC, dst)
        except PermissionError:
            print('   ⚠️ csx 复制被拒（已知间歇故障）；沿用旧副本')
    t0 = time.time()
    p = subprocess.Popen([EXE, 'load', dw, '-s', dst], cwd=CWD,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.read().decode('utf-8', 'replace')
    p.wait()
    print('[%s] rc=%d  %.1fs  |  %s' % (ch, p.returncode, time.time() - t0,
                                        out.strip().splitlines()[-1] if out.strip() else ''))
    lg = os.path.join(W, 'dump_log49.txt')
    if os.path.isfile(lg):
        lines = io.open(lg, encoding='utf-8').read().splitlines()
        miss = [l for l in lines if l.startswith('MISS')]
        print('   OK=%d MISS=%d' % (len(lines) - len(miss), len(miss)))
        for l in miss[:25]:
            print('     ', l.replace('\t', ' '))


if __name__ == '__main__':
    chs = sys.argv[1:] or ['chapter2_windows', 'chapter1_windows', 'chapter3_windows',
                           'chapter4_windows', 'chapter5_windows']
    for c in chs:
        run_ch(c)
