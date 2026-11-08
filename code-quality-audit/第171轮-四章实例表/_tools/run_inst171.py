# -*- coding: utf-8 -*-
"""第171轮 · 跑 inst171.csx 取某章逐房间实例快照。

★ 先拿 **ch2** 做 A/B 锚点：本章第42轮已有 `ch2_inst42.json`，
  只有在 `inst171` 能复现它的 rooms/insts 之后，才允许相信另外四章的结果。
  （「反汇编/解析器先过 A/B 锚点」—— 第168轮定下的规矩。）

用法:
  python run_inst171.py ch2          # 只跑 ch2（用于和 ch2_inst42.json 对账）
  python run_inst171.py ch1 ch3 ch4 ch5
  python run_inst171.py all

产物: `code-quality-audit/第171轮-四章实例表/_evidence/inst171.<ch>.json`
★ 绝不往 data.win 所在目录写任何东西（csx 从本目录 -s 传入，输出走环境变量）。
"""
import hashlib
import io
import os
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
CSX = os.path.join(HERE, 'inst171.csx')

UTMT_DIR = r'D:\E盘备份_20261028\Download\UTMT_CLI_v0.9.2.0'
UTMT = os.path.join(UTMT_DIR, 'UndertaleModCli.exe')
DRW = r'D:\E盘备份_20261028\Download\_tmp\drw'

CH2WIN = {
    'ch1': 'chapter1_windows',
    'ch2': 'chapter2_windows',
    'ch3': 'chapter3_windows',
    'ch4': 'chapter4_windows',
    'ch5': 'chapter5_windows',
}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def run(ch):
    win = CH2WIN[ch]
    wm = os.path.join(DRW, win, 'data.win')
    if not os.path.isfile(wm):
        print('[%s] 缺 data.win: %s' % (ch, wm))
        return False
    out = os.path.join(EV, 'inst171.%s.json' % ch)
    os.makedirs(EV, exist_ok=True)
    if os.path.exists(out):
        os.remove(out)
    before = sha(wm)
    env = dict(os.environ)
    env['INST171_OUT'] = out
    t = time.time()
    p = subprocess.Popen([UTMT, 'load', wm, '-s', CSX], cwd=UTMT_DIR,
                         stdin=subprocess.DEVNULL, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = p.stdout.read().decode('utf-8', 'replace')
    p.wait()
    dur = time.time() - t
    keep = [ln for ln in txt.splitlines() if 'inst171' in ln or 'Exception' in ln]
    print('[%s] rc=%d  %.1fs' % (ch, p.returncode, dur))
    for ln in (keep or txt.splitlines()[-6:]):
        print('    ' + ln)
    ok = os.path.isfile(out)
    if ok:
        print('    -> %s  %d B' % (os.path.basename(out), os.path.getsize(out)))
    print('    data.win 未改动: %s' % (before == sha(wm)))
    return ok


if __name__ == '__main__':
    args = sys.argv[1:] or ['all']
    if args == ['all']:
        args = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
    bad = [c for c in args if not run(c)]
    print('')
    print('完成 %d 章，失败 %d 章%s' % (len(args) - len(bad), len(bad),
                                       ('：' + ','.join(bad)) if bad else ''))
    sys.exit(0 if not bad else 1)
