# -*- coding: utf-8 -*-
"""第69轮 · 取证：仓库里 persona 文件的**换行风格**（HEAD blob 原始字节）。

背景
----
`extract_personas69.py --write` 之后，磁盘文件比旧索引 `_personas.json` 记的
`bytes`/`chars` 各多 8（例：asgore 10560→10568 / 4025→4033），但 `sha256_lf` 不变。
假设 = **尾块「本项目补充」的换行风格被改了**（旧 = LF，新 = CRLF）：
  * `autocrlf=true` ⇒ 两者 stage 后都是同一个全 LF blob ⇒ `git status` 只报 3 个 M；
  * LF 归一化后内容相同 ⇒ `sha256_lf` 不变；
  * 尾块 8 行 ⇒ 磁盘 +8 字节 / +8 字符。

本探针**不看工作区**（已被覆盖），直接取 HEAD 的 blob 原始字节来坐实：
`git ls-files -s` 拿 blob hash → `git cat-file blob` 拿**未经 smudge 的原始字节**。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
REL = 'ralsei_pet/assets/npc/persona'
PER = os.path.join(ROOT, REL)

# 取 3 个样本：1 个纯旧记录 + 2 个本轮真改的
SAMPLES = ['asgore', 'ut_chara', 'ut_toriel']


def blob_of(name):
    out = subprocess.run(['git', 'ls-files', '-s', '--', '%s/%s.txt' % (REL, name)],
                         cwd=ROOT, capture_output=True)
    line = out.stdout.decode('utf-8', 'replace').strip()
    if not line:
        return None
    return line.split()[1]


for name in SAMPLES:
    h = blob_of(name)
    if h is None:
        print('[SKIP] %s 未被 git 跟踪' % name)
        continue
    raw = subprocess.run(['git', 'cat-file', 'blob', h],
                         cwd=ROOT, capture_output=True).stdout
    t = raw.decode('utf-8', 'replace')
    n_lf = t.count('\n')
    n_crlf = t.count('\r\n')
    print('=== %s ===' % name)
    print('  HEAD blob: bytes=%d  \\n=%d  \\r\\n=%d  ⇒ 裸 LF=%d  \\r=%d'
          % (len(raw), n_lf, n_crlf, n_lf - n_crlf, t.count('\r')))
    disk = open(os.path.join(PER, name + '.txt'), 'rb').read()
    dt = disk.decode('utf-8', 'replace')
    print('  工作区   : bytes=%d  \\n=%d  \\r\\n=%d  ⇒ 裸 LF=%d  \\r=%d'
          % (len(disk), dt.count('\n'), dt.count('\r\n'),
             dt.count('\n') - dt.count('\r\n'), dt.count('\r')))
    # 找第一处裸 LF，打印上下文（应当正好是尾块开始处）
    m = re.search(r'(?<!\r)\n', t)
    if m:
        i = m.start()
        print('  第一处裸 LF @ 字符 %d，上文 = %r' % (i, t[max(0, i - 60):i + 2]))
    else:
        print('  （无裸 LF ⇒ 全 CRLF）')
    print('')
