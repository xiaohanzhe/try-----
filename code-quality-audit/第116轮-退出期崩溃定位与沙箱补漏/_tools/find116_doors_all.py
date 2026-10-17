# -*- coding: utf-8 -*-
u"""列出**全部**含「门」的用户短句原话（<400 字），按时间序（只读）。"""
import io
import json
import os
import re

ROOTS = [r'C:\Users\23002\.workbuddy\projects']
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
                if u'门' not in line:
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
                    if t and len(t) <= 400 and u'门' in t:
                        rows.append((o.get('timestamp'),
                                     os.path.basename(p)[:16], ln, t))

rows.sort(key=lambda r: (str(r[0]), r[2]))
print('含「门」短句原话 = %d 条' % len(rows))
for ts, base, ln, s in rows:
    print('[%s] %s:%d  %s' % (ts, base, ln, s.replace('\n', ' | ')))
