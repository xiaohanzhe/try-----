# -*- coding: utf-8 -*-
u"""第64轮 · 段1b：看清《其余人物设定.txt》的分块结构（只读）。

打印每个块的前 140 字 / 后 60 字，以及第一处 `你是X` 命中，判断"短块+长块"的配对关系。
"""
from __future__ import print_function
import io, re, sys

try:
    sys.stdout.reconfigure(encoding=u'utf-8', errors=u'replace')
except Exception:
    pass

SRC = u'C:\\Users\\23002\\Desktop\\其余人物设定.txt'
raw = io.open(SRC, 'rb').read().decode('utf-8', 'replace').replace(u'\r\n', u'\n')
parts = re.split(u'^\\s*-{3,}\\s*$', raw, flags=re.M)

LO = int(sys.argv[1]) if len(sys.argv) > 1 else 0
HI = int(sys.argv[2]) if len(sys.argv) > 2 else 14

print(u'总块数 = %d' % len(parts))
for i, p in enumerate(parts):
    if not (LO <= i <= HI):
        continue
    t = p.strip()
    m = re.search(u'你是\\s*([^，,。！!？?\\n【】]{1,16}?)\\s*[，,。]', t)
    ix = re.search(u'【角色身份】\\s*([^【]{0,90})', t)
    print(u'--- 块 %d  (chars=%d) ---' % (i, len(t)))
    print(u'  head: %s' % t[:140].replace(u'\n', u' / '))
    if m:
        print(u'  `你是X` -> %r' % (m.group(1),))
    if ix:
        print(u'  【角色身份】-> %s' % ix.group(1).replace(u'\n', u' ')[:90])
    print()
