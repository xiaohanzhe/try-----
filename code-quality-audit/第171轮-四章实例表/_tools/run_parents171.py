# -*- coding: utf-8 -*-
"""第171轮 · 跑 parents171.csx（门对象继承链 + 自身是否有 Alarm 代码）。

用法: python run_parents171.py ch2
产物: `_evidence/parents171.<ch>.json`
"""
import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
CSX = os.path.join(HERE, 'parents171.csx')

UTMT_DIR = r'D:\E盘备份_20261028\Download\UTMT_CLI_v0.9.2.0'
UTMT = os.path.join(UTMT_DIR, 'UndertaleModCli.exe')
DRW = r'D:\E盘备份_20261028\Download\_tmp\drw'
WIN = {'ch1': 'chapter1_windows', 'ch2': 'chapter2_windows',
       'ch3': 'chapter3_windows', 'ch4': 'chapter4_windows',
       'ch5': 'chapter5_windows'}


def run(ch):
    wm = os.path.join(DRW, WIN[ch], 'data.win')
    out = os.path.join(EV, 'parents171.%s.json' % ch)
    if os.path.exists(out):
        os.remove(out)
    env = dict(os.environ)
    env['INST171_PARENTS'] = out
    p = subprocess.Popen([UTMT, 'load', wm, '-s', CSX], cwd=UTMT_DIR,
                         stdin=subprocess.DEVNULL, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = p.stdout.read().decode('utf-8', 'replace')
    p.wait()
    keep = [ln for ln in txt.splitlines() if 'parents171' in ln or 'Exception' in ln]
    print('[%s] rc=%d' % (ch, p.returncode))
    for ln in (keep or txt.splitlines()[-5:]):
        print('    ' + ln)
    return os.path.isfile(out)


if __name__ == '__main__':
    args = sys.argv[1:] or ['ch2']
    bad = [c for c in args if not run(c)]
    sys.exit(0 if not bad else 1)
