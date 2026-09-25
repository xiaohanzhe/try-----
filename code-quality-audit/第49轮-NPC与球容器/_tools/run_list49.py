# -*- coding: utf-8 -*-
"""第49轮 · 跑 list_names49.csx（枚举全部 code/obj/spr 名）并按关键词过滤。

用法:
    C:\\Python311\\python.exe run_list49.py                 # 五章全跑
    C:\\Python311\\python.exe run_list49.py 2 3             # 只跑 ch2 ch3
产出:
    <data.win 同级>/names49.txt         （原始全量清单）
    _evidence/names49/ch<N>_hits.txt    （关键词过滤结果，蒸馏进仓库）
"""
import io
import os
import re
import shutil
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
EXE = r'E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe'
CWD = r'E:\Download\UTMT_CLI_v0.9.2.0'
DRW = r'E:\Download\_tmp\drw'
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
SRC = os.path.join(HERE, 'list_names49.csx')
DEST = os.path.join(ROUND, '_evidence', 'names49')

# 过滤器：只看与 NPC / 跟随 / 球容器 / 世界门控 有关的名字
KW = ('capsule', 'gacha', 'ballcon', 'ball', 'npc_', 'follower', 'following',
      'follow_', '_follow', 'party', 'caterpillar', 'darkzone', 'world_',
      'toriel', 'asgore', 'lancer', 'king', 'queen', 'tenna', 'spamton',
      'berdly', 'gerson', 'mike', 'jevil', 'knight', 'ralsei', 'susie', 'kris',
      'throwkris', 'puton', 'mask', 'bubble', 'filter', 'clip', 'hang')
RX = re.compile('|'.join(re.escape(k) for k in KW), re.I)


def _safe_write(path, text, tries=6):
    last = None
    for _ in range(tries):
        try:
            with io.open(path, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)
            return True
        except OSError as e:
            last = e
            time.sleep(0.6)
    print('   !! 写入失败 %s : %s' % (path, last))
    return False


def run_ch(idx):
    ch = 'chapter%d_windows' % idx
    W = os.path.join(DRW, ch)
    dw = os.path.join(W, 'data.win')
    if not os.path.isfile(dw):
        print('[%s] 缺少 data.win' % ch)
        return None
    sdir = os.path.join(W, 'scripts')
    if not os.path.isdir(sdir):
        os.makedirs(sdir)
    dst = os.path.join(sdir, 'list_names49.csx')
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
    ns = os.path.join(W, 'names49.txt')
    n = 0
    if os.path.isfile(ns):
        for i in range(4):
            try:
                lines = io.open(ns, encoding='utf-8', errors='replace').read().splitlines()
                break
            except OSError:
                lines = []
                time.sleep(0.7)
        hits = [l for l in lines if RX.search(l)]
        n = len(lines)
        os.makedirs(DEST, exist_ok=True) if not os.path.isdir(DEST) else None
        _safe_write(os.path.join(DEST, 'ch%d_hits.txt' % idx),
                    '# %s 全量 %d 行；关键词命中 %d 行\n%s\n'
                    % (ch, n, len(hits), '\n'.join(hits)))
    print('[%s] rc=%d %.1fs 全量行=%d' % (ch, p.returncode, time.time() - t0, n))


if __name__ == '__main__':
    idxs = [int(a) for a in sys.argv[1:]] or [1, 2, 3, 4, 5]
    for i in idxs:
        run_ch(i)
