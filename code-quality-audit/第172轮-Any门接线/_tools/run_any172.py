# -*- coding: utf-8 -*-
"""第172轮 · 跑 probe_any172.csx 探 obj_doorAny（**只读**）。

★ 先用 ch2 验管线（第42轮 `ch2_inst42.json` 和第171轮 `inst171.ch2.json` 都在，
  能当场对账「我数出来的 Any 门实例 == 那两份里 obj_doorAny 那部分」），
  管线过了才铺开四章。

用法:
  python run_any172.py ch2
  python run_any172.py ch1 ch3 ch4 ch5
  python run_any172.py all
  python run_any172.py ch2 --csx=probe2_172      # 换脚本（产物名跟着换）

产物: `第172轮-Any门接线/_evidence/<csx 名>.<ch>.json`
★ 绝不往 data.win 所在目录写任何东西（csx 从仓库内 -s 传入，输出走环境变量）。
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

STEM = 'probe_any172'
ARGS = []
for a in sys.argv[1:]:
    if a.startswith('--csx='):
        STEM = a.split('=', 1)[1]
    else:
        ARGS.append(a)
CSX = os.path.join(HERE, STEM + '.csx')


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
    out = os.path.join(EV, '%s.%s.json' % (STEM, ch))
    os.makedirs(EV, exist_ok=True)
    if os.path.exists(out):
        os.remove(out)
    before = sha(wm)
    env = dict(os.environ)
    env['PROBE172_OUT'] = out
    t = time.time()
    p = subprocess.Popen([UTMT, 'load', wm, '-s', CSX], cwd=UTMT_DIR,
                         stdin=subprocess.DEVNULL, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = p.stdout.read().decode('utf-8', 'replace')
    p.wait()
    dur = time.time() - t
    keep = [ln for ln in txt.splitlines() if 'probe172' in ln or 'Exception' in ln]
    print('[%s] rc=%d  %.1fs' % (ch, p.returncode, dur))
    for ln in (keep or txt.splitlines()[-6:]):
        print('    ' + ln)
    ok = os.path.isfile(out)
    if ok:
        print('    -> %s  %d B' % (os.path.basename(out), os.path.getsize(out)))
    print('    data.win 未改动: %s' % (before == sha(wm)))
    return ok


if __name__ == '__main__':
    args = ARGS or ['all']
    if args == ['all']:
        args = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
    bad = [c for c in args if not run(c)]
    print('')
    print('完成 %d 章，失败 %d 章%s' % (len(args) - len(bad), len(bad),
                                       ('：' + ','.join(bad)) if bad else ''))
    sys.exit(0 if not bad else 1)
