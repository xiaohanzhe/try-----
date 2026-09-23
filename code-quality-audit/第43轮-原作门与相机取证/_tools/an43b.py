# -*- coding: utf-8 -*-
"""第43轮 · 通用：把 *_codes.txt 里指定 code 的指令流渲染成可读文本

用法: python an43b.py <codes.txt 绝对路径> [要匹配的 code 名子串 ...]
"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
SRC = sys.argv[1]
want = [w.lower() for w in sys.argv[2:]] or ['__view_set_internal']

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
                            'fn', 'var', 'ref', 'jnk']):
        if i + 1 < len(cells):
            c = cells[i + 1]
            if '=' in c:
                k2, v2 = c.split('=', 1)
                d[nm] = v2
            else:
                d[nm] = c
    blocks[cur].append(d)


def render(d):
    kind = d.get('kind', '')
    fn = d.get('fn', '')
    var = d.get('var', '')
    t1 = d.get('T1', '')
    if fn:
        return 'CALL %s' % fn
    if var:
        return 'VAR  %s   [kind=%s t1=%s]' % (var, kind, t1)
    if kind == 'Cmp':
        return 'CMP  t1=%s t2=%s' % (t1, d.get('T2', ''))
    if kind in ('B', 'Bf'):
        return 'JMP  off=%s' % d.get('jnk', '')
    if kind.startswith('Push'):
        parts = []
        for f in ('I', 'S', 'L', 'D'):
            v = d.get(f, '')
            if v not in ('', '0', 'None'):
                parts.append('%s=%s' % (f, v))
        return 'PUSH %s  %s' % (kind, ' '.join(parts) if parts else
                                'I=%s S=%s' % (d.get('I', ''), d.get('S', '')))
    return kind


print('SOURCE = %s ；code 数 = %d' % (SRC, len(blocks)))
print('-' * 78)
n = 0
for name in blocks:
    low = name.lower()
    if not any(w in low for w in want):
        continue
    ins = blocks[name]
    n += 1
    print('### %s   ins=%d' % (name, len(ins)))
    for d in ins:
        print('   %4s  %s' % (d['k'], render(d)))
    print()
print('[匹配 %d 个 code]' % n)
