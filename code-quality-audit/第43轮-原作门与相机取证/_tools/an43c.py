# -*- coding: utf-8 -*-
"""第43轮 · 在长函数里按关键词定位（打印命中行 ± 上下文）

用法: python an43c.py <codes.txt> <code 名子串> [关键词 ...]
"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
SRC = sys.argv[1]
name = sys.argv[2]
kws = [k.lower() for k in sys.argv[3:]] or ['view', 'cam', 'shake', 'room', 'pan']

blocks = {}
cur = None
head = re.compile(r'^###\s+(\S+)\s+ins=(\d+)$')
for line in open(SRC, encoding='utf-8'):
    line = line.rstrip('\n')
    m = head.match(line)
    if m:
        cur = m.group(1)
        blocks[cur] = []
        continue
    if cur is None or not line.startswith('  '):
        continue
    cells = line.strip().split('\t')
    d = {'k': cells[0]}
    for i, nm in enumerate(['kind', 'T1', 'T2', 'S', 'I', 'L', 'D',
                            'fn', 'var', 'ref', 'jnk', 's']):
        if i + 1 < len(cells):
            c = cells[i + 1]
            d[nm] = c.split('=', 1)[1] if '=' in c else c
    blocks[cur].append(d)


def render(d):
    if d.get('fn'):
        return 'CALL %s' % d['fn']
    if d.get('var'):
        return 'VAR  %s' % d['var']
    kind = d.get('kind', '')
    if kind == 'Cmp':
        return 'CMP'
    if kind in ('B', 'Bf'):
        return 'JMP'
    if kind.startswith('Push'):
        parts = [f + '=' + d.get(f, '') for f in ('I', 'L', 'D') if d.get(f) not in (None, '', '0')]
        return 'PUSH %s' % (' '.join(parts) if parts else '')
    return kind


matched = [k for k in blocks if name.lower() in k.lower()]
for cn in matched:
    ins = blocks[cn]
    print('############ %s   ins=%d ############' % (cn, len(ins)))
    hits = []
    for i, d in enumerate(ins):
        t = (render(d) + ' ' + str(d.get('s', ''))).lower()
        if any(k in t for k in kws):
            hits.append(i)
    if not hits:
        print('   (无命中)')
        continue
    print('   命中 %d 行' % len(hits))
    shown = set()
    for h in hits:
        for j in range(max(0, h - 1), min(len(ins), h + 2)):
            shown.add(j)
    prev = -2
    for j in sorted(shown):
        if j != prev + 1:
            print('   ......')
        print('   %5d  %s' % (j, render(ins[j])))
        prev = j
    print()
