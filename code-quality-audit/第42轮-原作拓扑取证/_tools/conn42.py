# -*- coding: utf-8 -*-
"""第42轮 · 从 probe42_codes.txt 复原原作「房间连接表」
模式：PushBltn(room) / PushI(X) / Cmp / Bf ... PushI(Y) / Conv / Call(room_goto)
"""
import io
import json
import os
import re
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
TXT = r'E:\Download\_tmp\drw\chapter1_windows\probe42_codes.txt'
OUT = r'E:\Download\_tmp\conn42.json'
ROOMS = r'E:\Download\_tmp\drw\chapter1_windows\rooms_map.json'

rnames = [r['name'] for r in json.loads(open(ROOMS, 'rb').read().decode('utf-8'))['rooms']]


def rn(i):
    return rnames[i] if 0 <= i < len(rnames) else '?%d' % i


lines = open(TXT, 'rb').read().decode('utf-8').splitlines()

cur = None
pairs = []            # (src, dst, code, ev)
direct = []           # (None, dst, code)
nextprev = []         # (code, kind)
pushes = []
src = None

RE_HEAD = re.compile(r'^###\s+(\S+)\s+ins=(\d+)$')
RE_INS = re.compile(r'^\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s*(.*)$')

for ln in lines:
    m = RE_HEAD.match(ln)
    if m:
        cur = m.group(1)
        pushes = []
        src = None
        continue
    if cur is None:
        continue
    m = RE_INS.match(ln)
    if not m:
        continue
    idx, kind, t1, t2, extra = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5).strip()
    if kind.startswith('Push'):
        pushes.append((kind, t1, extra))
        if len(pushes) > 4:
            pushes.pop(0)
    elif kind == 'Cmp':
        if len(pushes) >= 2:
            a, b = pushes[-2], pushes[-1]
            if a[0] == 'PushBltn' and a[2] == 'VAR=room' and b[0].startswith('PushI'):
                try:
                    src = int(b[2])
                except ValueError:
                    src = None
            else:
                src = None
        pushes = []
    elif kind == 'Call':
        fn = extra[3:] if extra.startswith('FN=') else ''
        if fn == 'room_goto':
            dst = None
            if pushes and pushes[-1][0].startswith('PushI'):
                try:
                    dst = int(pushes[-1][2])
                except ValueError:
                    dst = None
            if dst is not None:
                if src is None:
                    direct.append((dst, cur))
                else:
                    pairs.append((src, dst, cur))
        elif fn in ('room_goto_next', 'room_goto_previous'):
            nextprev.append((cur, fn))
        pushes = []

print('=' * 78)
print('A. 带条件 (room == X) → room_goto(Y) 的配对表')
print('=' * 78)
by_code = defaultdict(list)
for s, d, c in pairs:
    by_code[c].append((s, d))
print('  总对=%d  涉及 Code 条目=%d' % (len(pairs), len(by_code)))
for c in sorted(by_code):
    ps = by_code[c]
    print('\n  ## %s   pairs=%d' % (c, len(ps)))
    for s, d in ps:
        print('      %-26s -> %-26s   (%d -> %d)' % (rn(s), rn(d), s, d))

print()
print('=' * 78)
print('B. 无条件 room_goto(Y)（current room 未知）')
print('=' * 78)
for d, c in direct:
    print('   %-44s -> %-26s (%d)' % (c, rn(d), d))

print()
print('=' * 78)
print('C. room_goto_next / previous')
print('=' * 78)
for c, f in nextprev:
    print('   %-44s %s' % (c, f))

# ---- 汇总成「无向边表」：只保留 src<dst 的去重，判断是否互补成对 ----
print()
print('=' * 78)
print('D. 双向成对性检验（同一 Code 内 X->Y 与 Y->X 是否都在）')
print('=' * 78)
for c in sorted(by_code):
    S = set()
    for s, d in by_code[c]:
        S.add((s, d))
    both, one = [], []
    seen = set()
    for s, d in sorted(S):
        if (s, d) in seen:
            continue
        if (d, s) in S:
            both.append((s, d))
            seen.add((s, d))
            seen.add((d, s))
        else:
            one.append((s, d))
            seen.add((s, d))
    print('\n  ## %s  双向对=%d  单向=%d' % (c, len(both), len(one)))
    for s, d in both:
        print('      <=> %-24s  %-24s' % (rn(s), rn(d)))
    for s, d in one:
        print('      --> %-24s -> %-24s' % (rn(s), rn(d)))

json.dump({'pairs': pairs, 'direct': direct, 'nextprev': nextprev},
          open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n落盘: %s (%d B)' % (OUT, os.path.getsize(OUT)))
