# -*- coding: utf-8 -*-
"""第68轮 · 跑 inst68.csx（五章），并把产物蒸馏进仓库 _evidence/。

用法: python run_inst68.py [chapter1_windows chapter2_windows ...]
      （不给参数 = 五章全跑）

为什么要有这个 runner（而不是手敲 CLI）
----------------------------------------
1. UTMT CLI 必须 **cwd = 它自己的目录**（依赖同目录的 dll）；
2. 脚本要**先复制进 data.win 同级 `scripts/`**（CLI 只认相对可执行目录的路径）；
3. 必须核验 **data.win 未被改动**（原版文件，改了就毁了取证基线）；
4. ★ 产物必须**蒸馏进仓库** `_evidence/`（记忆铁律：回归不许依赖临时区／外部盘）。
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
ROOT = os.path.join(HERE, '..', '..', '..')
SRC = os.path.join(HERE, 'inst68.csx')
EV = os.path.join(ROOT, 'code-quality-audit', '第68轮-可交互道具实例补采', '_evidence')

CHS = sys.argv[1:] or ['chapter1_windows', 'chapter2_windows', 'chapter3_windows',
                       'chapter4_windows', 'chapter5_windows']
#: ch1 的实例产物在第42轮就叫 `inst42.json`（无章节前缀），沿用这个命名习惯。
OUTNAME = {'chapter1_windows': 'inst68.json'}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


os.makedirs(EV, exist_ok=True)
summary = []

for ch in CHS:
    W = os.path.join(DRW, ch)
    wm = os.path.join(W, 'data.win')
    if not os.path.isfile(wm):
        print('[%s] !! 缺少 data.win' % ch)
        summary.append((ch, 'NO_DATA'))
        continue
    before = sha(wm)
    sdir = os.path.join(W, 'scripts')
    os.makedirs(sdir, exist_ok=True)
    dst = os.path.join(sdir, 'inst68.csx')
    shutil.copyfile(SRC, dst)

    t = time.time()
    p = subprocess.Popen([EXE, 'load', wm, '-s', dst], cwd=CWD,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.read().decode('utf-8', 'replace')
    p.wait()
    print('[%s] rc=%d  %.1fs' % (ch, p.returncode, time.time() - t))
    print(out[-1200:])
    unchanged = (before == sha(wm))
    print('data.win 未改动: %s' % unchanged)
    if not unchanged:
        summary.append((ch, 'DATA_WIN_MUTATED'))
        continue

    src = os.path.join(W, 'inst68.json')
    if not os.path.isfile(src):
        summary.append((ch, 'NO_OUTPUT'))
        continue
    oname = OUTNAME.get(ch, 'ch%s_inst68.json' % ch[len('chapter'):len('chapter') + 1])
    shutil.copyfile(src, os.path.join(EV, oname))
    print('  -> _evidence/%s  %d B' % (oname, os.path.getsize(src)))
    summary.append((ch, oname))

print('')
print('=== 汇总 ===')
for ch, r in summary:
    print('%-18s %s' % (ch, r))
