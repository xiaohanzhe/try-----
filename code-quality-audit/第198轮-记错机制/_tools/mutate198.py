# -*- coding: utf-8 -*-
"""第198轮 · 变异测试：`check198` 的判据**真的会红**吗。

规矩（第85/129/191/196 轮反复钉的）
-----------------------------------
· 每条变异必须让**红数 > 0 且 < 25** —— 只红一两条说明判据太窄，
  红一大片说明打断的是别处（不是被测性质）。
· **必须有一条无害变异红 0**（只改注释）—— 否则"红"可能只是文件被动过。
· 每个文件整字节还原并核 sha1（**不许** `replace(old, new, 1)` 这种锚点松的写法）。
· 锚点按**文件自己的换行符**组装：本项目源码是 CRLF，写 `\n` 会"锚点出现 0 次"（假红）。
"""
from __future__ import print_function

import hashlib
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
CHECK = os.path.join(HERE, 'check198.py')
PY = sys.executable

TOTAL = 25

MUTATIONS = [
    ('M1 关键记忆不再豁免（重要的事也会记偏）',
     'modules/memory_system.py',
     "            if it.get('is_key') or it.get('is_digest'):\n                return ''\n",
     "            if it.get('is_digest'):\n                return ''\n",
     'B1 / E3 必须红'),

    ('M2 日摘要不再豁免',
     'modules/memory_system.py',
     "            if it.get('is_key') or it.get('is_digest'):\n                return ''\n",
     "            if it.get('is_key'):\n                return ''\n",
     'B2 必须红'),

    ('M3 受保护的 kind 不再豁免（成就/升级会被说走样）',
     'modules/memory_system.py',
     "            if kind == 'inner' or kind in self.PROTECTED_KINDS:\n                return ''\n",
     "            if kind == 'inner':\n                return ''\n",
     'B3 必须红'),

    ('M4 内在活动不再豁免（会叠两层"好像"）',
     'modules/memory_system.py',
     "            if kind == 'inner' or kind in self.PROTECTED_KINDS:\n                return ''\n",
     "            if kind in self.PROTECTED_KINDS:\n                return ''\n",
     'B4 必须红'),

    ('M5 触发率被设成 0（整机制变成死的）',
     'modules/memory_system.py',
     "    MISFIRE_RATE = 0.30",
     "    MISFIRE_RATE = 0.0",
     'A1 / B5 必须红'),

    ('M6 换成 random（回归不可重放）',
     'modules/memory_system.py',
     "            h = hashlib.sha1(seed.encode('utf-8', 'ignore')).hexdigest()\n",
     "            import random\n            h = hashlib.sha1((seed + str(random.random())).encode('utf-8', 'ignore')).hexdigest()\n",
     'F3 / D1 必须红'),

    ('M7 SOFTEN 开始编造数字',
     'modules/memory_system.py',
     "                continue\n        return out.strip()\n",
     "                continue\n        return (out + u' 3').strip()\n",
     'C1 必须红'),

    ('M8 触发条件反了（RATE=0 反而全走样、RATE=1 反而全不走样）',
     'modules/memory_system.py',
     "            if (int(h[:8], 16) / 4294967296.0) >= rate:\n                return ''\n",
     "            if (int(h[:8], 16) / 4294967296.0) <= rate:\n                return ''\n",
     'B5 / B6 必须红'),

    ('M9 无害变异：只给注释补一个句号',
     'modules/memory_system.py',
     "    MISFIRE_SALT = 'ralsei-misfire-1'",
     "    MISFIRE_SALT = 'ralsei-misfire-1'  # \u6ce8\u91ca",
     '必须红 0'),
]


def sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for c in iter(lambda: f.read(65536), b''):
            h.update(c)
    return h.hexdigest()


def run_check():
    p = subprocess.Popen([PY, CHECK], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, cwd=HERE)
    out = p.communicate()[0].decode('utf-8', 'replace')
    m = re.search(r'PASS=(\d+)\s+FAIL=(\d+)', out)
    if not m:
        return None, None, out
    return int(m.group(1)), int(m.group(2)), out


def main():
    print('=' * 78)
    print('第198轮变异测试')
    print('=' * 78)
    p0, f0, out0 = run_check()
    if p0 is None:
        print('[FAIL] 基线跑不起来：\n%s' % out0[-2000:])
        return 2
    print('基线：PASS=%d FAIL=%d' % (p0, f0))
    if f0 != 0:
        print('[FAIL] 基线本身就红，先修再变异')
        return 2
    if p0 + f0 != TOTAL:
        print('[FAIL] 基线条数 %d != 声明 %d' % (p0 + f0, TOTAL))
        return 2

    ok = 0
    for label, rel, old, new, expect in MUTATIONS:
        path = os.path.join(PET, rel.replace('/', os.sep))
        raw = io.open(path, 'rb').read()
        before = sha1(path)
        try:
            text = raw.decode('utf-8')
        except Exception as e:
            print('[FAIL] %-46s 读不出源码：%s' % (label, e))
            continue
        nl = '\r\n' if b'\r\n' in raw else '\n'
        old = old.replace('\n', nl)
        new = new.replace('\n', nl)
        n = text.count(old)
        if n != 1:
            print('[FAIL] %-46s 锚点出现 %d 次（必须恰好 1 次）' % (label, n))
            continue
        io.open(path, 'wb').write(text.replace(old, new).encode('utf-8'))
        try:
            p, f, out = run_check()
        finally:
            io.open(path, 'wb').write(raw)
        if sha1(path) != before:
            print('[FAIL] %-46s 还原后 sha1 不一致（文件已脏）' % label)
            return 3
        if p is None:
            print('[FAIL] %-46s 跑崩了' % label)
            continue
        good = (f == 0) if ('红 0' in expect) else (0 < f < TOTAL)
        print('[%s] %-46s 红 %d / %d   (%s)'
              % ('PASS' if good else 'FAIL', label, f, TOTAL, expect))
        if good:
            ok += 1

    print('\n变异 %d / %d 符合预期' % (ok, len(MUTATIONS)))
    return 0 if ok == len(MUTATIONS) else 1


if __name__ == '__main__':
    sys.exit(main())
