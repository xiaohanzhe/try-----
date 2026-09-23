# -*- coding: utf-8 -*-
"""第43轮 · 把 func43b_codes.txt 里指定 code 的指令流渲染成可读文本

用法: python an43.py <chapter1_windows> [要打印的 code 名子串 ...]
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
W = os.path.join(r'E:\Download\_tmp\drw',
                 sys.argv[1] if len(sys.argv) > 1 else 'chapter1_windows')
SRC = os.path.join(W, 'func43b_codes.txt')

want = sys.argv[2:] or ['__view_get', '__view_set_internal', 'backgrounder_standard_Other_10']
want = [w.lower() for w in want]

# ---- 解析 ----
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
    # cells: k, Kind, T1=, T2=, S=, I=, L=, D=, fn=, var=, ref=, jnk=
    d = {}
    d['k'] = cells[0]
    d['kind'] = cells[1] if len(cells) > 1 else ''
    for c in cells[2:]:
        if '=' in c:
            k2, v2 = c.split('=', 1)
            d[k2] = v2
    blocks[cur].append(d)


def render(d):
    kind = d.get('kind', '')
    fn = d.get('fn', '')
    var = d.get('var', '')
    t1 = d.get('T1', '')
    jnk = d.get('jnk', '')
    if fn:
        return 'CALL %s  (t1=%s)' % (fn, t1)
    if var:
        return 'VAR  %s  (kind=%s t1=%s)' % (var, kind, t1)
    if kind == 'Cmp':
        return 'CMP  (t1=%s t2=%s)' % (t1, d.get('T2', ''))
    if kind in ('B', 'Bf'):
        return 'JMP  off=%s' % jnk
    if kind.startswith('Push'):
        v = ''
        for f in ('I', 'S', 'L', 'D'):
            if d.get(f) and d.get(f) != '0':
                v = '%s=%s' % (f, d.get(f))
                break
        if not v:
            v = 'I=%s S=%s' % (d.get('I', ''), d.get('S', ''))
        return 'PUSH %s  %s' % (kind, v)
    return kind


print('func43b_codes.txt 中 code 数 = %d' % len(blocks))
print('-' * 78)
for name in blocks:
    low = name.lower()
    if not any(w in low for w in want):
        continue
    ins = blocks[name]
    print('### %s   ins=%d' % (name, len(ins)))
    for d in ins:
        print('   %4s  %s' % (d['k'], render(d)))
    print()
