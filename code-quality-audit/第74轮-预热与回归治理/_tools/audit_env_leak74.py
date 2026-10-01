# -*- coding: utf-8 -*-
"""B11 取证：**进入比对的那份文本**里有没有真实环境泄漏（= 非密闭）。

为什么必须用 run_all.normalize()
--------------------------------
第一版直接扫 `_out/<id>.txt`（**原始**输出）⇒ 满屏 `C:\\Users\\23002\\AppData\\...`，
看着像一堆套件在碰真实环境。其实 `normalize()` 早就把这些换成了 `<TMP>`，
**基线里根本没有**。⇒ 拿原始文本当判据 = 又一个"判据口径不对"的假问题。
（本项目第 N 次：判据本身也是被测物。）

所以本脚本**直接 import run_all，调它自己的 `normalize()`**（单一真源，不重写）。

判据：
  L1 `E:\\RalseiMemory`  —— 真实保管库路径**活到了比对阶段**（真泄漏）
  L2 未归一化的临时目录（`AppData\\Local\\Temp` 后仍跟随机名）
  L3 网络 / Ollama 端点
  L4 归一化后仍残留的绝对路径
"""
import io
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
REG = os.path.join(ROOT, 'code-quality-audit', 'regress')
OUT = os.path.join(REG, '_out')
if REG not in sys.path:
    sys.path.insert(0, REG)

import run_all  # noqa: E402  （单一真源：用它自己的 normalize）

L1 = re.compile(r'[Ee]:[\\/]+RalseiMemory')
L2 = re.compile(r'AppData[\\/]+Local[\\/]+Temp[\\/]+[A-Za-z0-9_]')
L3 = re.compile(r'127\.0\.0\.1|localhost|:11434')
L4 = re.compile(r'[A-Za-z]:[\\/]{1,2}[^"\'\s<>]{3,}')

PAT = [('L1 真实保管库 E:\\RalseiMemory', L1),
       ('L2 未归一的临时目录', L2),
       ('L3 网络/Ollama', L3),
       ('L4 其它绝对路径', L4)]

rows = []
for fn in sorted(os.listdir(OUT)):
    if not fn.endswith('.txt'):
        continue
    sid = fn[:-4]
    if sid.endswith('.diff'):
        continue
    raw = io.open(os.path.join(OUT, fn), encoding='utf-8', errors='replace').read()
    norm = run_all.normalize(raw)
    hits = {}
    for label, rx in PAT:
        found = sorted(set(rx.findall(norm)))
        if found:
            hits[label] = (len(found), found[:3])
    rows.append((sid, hits, len(raw.splitlines()), len(norm.splitlines())))

print('=' * 78)
print('B11 取证（**归一化后**的比对文本，与基线同口径）')
print('=' * 78)
dirty = [r for r in rows if r[1]]
for sid, hits, nr, nn in rows:
    if hits:
        print('XX %-22s raw=%4d norm=%4d' % (sid, nr, nn))
        for label, (cnt, sample) in hits.items():
            print('     %-28s x%d  e.g. %s' % (label, cnt, sample))
print('-' * 78)
print('归一化后仍泄漏的套件数 = %d / %d' % (len(dirty), len(rows)))
print('=' * 78)
