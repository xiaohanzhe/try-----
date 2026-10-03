# -*- coding: utf-8 -*-
u"""从 dr84_code_dump.txt 里抽出指定名字的代码原文。"""
from __future__ import print_function
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
DUMP = os.path.join(ROUND, u'_evidence', u'dr84_code_dump.txt')

names = sys.argv[1:]
txt = io.open(DUMP, u'r', encoding=u'utf-8').read()
blocks = re.split(u'\n={78}\n### ', txt)
got = {}
for b in blocks:
    m = re.match(u'([^\n]+?)\s+\((\d+) chars\)\n={78}\n', b)
    if not m:
        continue
    got[m.group(1).strip()] = (int(m.group(2)), b[m.end():])

if not names:
    for k in sorted(got):
        print(u'%7d  %s' % (got[k][0], k))
    sys.exit(0)

for n in names:
    if n not in got:
        print(u'!! 未找到: %s' % n); continue
    ln, src = got[n]
    print(u'\n' + u'#' * 78)
    print(u'## %s  (%d chars)' % (n, ln))
    print(u'#' * 78)
    print(src.rstrip(u'\n'))
