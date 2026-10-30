# -*- coding: utf-8 -*-
u"""★ 第116轮取证：用户门形态**短句原话**，按时间序（只读）。

★ 关键修正：用户真话在 jsonl 里被包成 `<user_query>…</user_query>`
  （可能前面还有 `<system-reminder>` 块）⇒ **不能**用"以 `<` 开头就跳过"，
  那会把全部用户原话过滤掉（第一版就是这么 0 命中的）。
"""
import io
import json
import os
import re

ROOTS = [r'C:\Users\23002\.workbuddy\projects']
KEY = [u'门框', u'任意门', u'门的形式', u'门也不是', u'门都不是', u'门长',
       u'门大']
UQ = re.compile(u'<user_query>(.*?)</user_query>', re.S)
rows = []


def walk(d):
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isdir(p):
            for q in walk(p):
                yield q
        elif name.endswith('.jsonl'):
            yield p


for root in ROOTS:
    for p in walk(root):
        with io.open(p, encoding='utf-8', errors='replace') as fh:
            for ln, line in enumerate(fh, 1):
                line = line.strip()
                if not line or not any(k in line for k in KEY):
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if not isinstance(o, dict):
                    continue
                if o.get('type') != 'message' or o.get('role') != 'user':
                    continue
                c = o.get('content')
                s = ''
                if isinstance(c, list):
                    for it in c:
                        if isinstance(it, dict):
                            s += it.get('text') or ''
                elif isinstance(c, str):
                    s = c
                if not s:
                    continue
                for m in UQ.finditer(s):
                    t = m.group(1).strip()
                    if t and len(t) <= 400:
                        rows.append((o.get('timestamp'),
                                     os.path.basename(p), ln, t))

rows.sort(key=lambda r: (str(r[0]), r[2]))
print('短句原话 = %d 条（按时间序）' % len(rows))
for ts, base, ln, s in rows:
    print('[%s] %s :%d' % (ts, base[:24], ln))
    print('    %s' % s.replace('\n', ' | '))
