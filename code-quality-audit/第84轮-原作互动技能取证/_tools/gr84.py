# -*- coding: utf-8 -*-
u"""按关键词在指定 code 段里 grep 出行号 + 上下文。"""
from __future__ import print_function
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
DUMP = os.path.join(ROUND, u'_evidence', u'dr84_code_dump.txt')

name = sys.argv[1]
pats = sys.argv[2:]
ctx = 3

txt = io.open(DUMP, u'r', encoding=u'utf-8').read()
blocks = re.split(u'\n={78}\n### ', txt)
src = None
for b in blocks:
    m = re.match(u'([^\n]+?)\s+\((\d+) chars\)\n={78}\n', b)
    if m and m.group(1).strip() == name:
        src = b[m.end():]
        break
if src is None:
    print(u'!! 未找到 %s' % name); sys.exit(1)

lines = src.split(u'\n')
for i, ln in enumerate(lines):
    for p in pats:
        if p in ln:
            print(u'--- line %d (/%d) ---' % (i, len(lines)))
            lo = max(0, i - ctx); hi = min(len(lines), i + ctx + 1)
            for j in range(lo, hi):
                mark = u'>>' if j == i else u'  '
                print(u'%s %5d | %s' % (mark, j, lines[j]))
            print(u'')
            break
