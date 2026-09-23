# -*- coding: utf-8 -*-
"""按 `## N.` 小节统计 MEMORY.md 字符占比，并按需裁剪排序。"""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
P = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')

text = open(P, encoding='utf-8').read()
print('TOTAL chars=%d bytes=%d  (target<=11000)' % (len(text), os.path.getsize(P)))

lines = text.split('\n')
cur = '(头部)'
buckets = {}
order = []
for ln in lines:
    if ln.startswith('## '):
        cur = ln[:34]
        order.append(cur)
        buckets.setdefault(cur, 0)
    buckets[cur] = buckets.get(cur, 0) + len(ln) + 1

for k in ['(头部)'] + order:
    v = buckets.get(k, 0)
    print('%6d  %5.1f%%  %s' % (v, 100.0 * v / len(text), k))
