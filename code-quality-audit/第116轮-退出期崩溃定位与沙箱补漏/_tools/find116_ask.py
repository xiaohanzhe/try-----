# -*- coding: utf-8 -*-
u"""★ 第116轮取证：把 AskUserQuestion 的**问题 + 用户选择**按时间序挖出来。

只认 tool_use(AskUserQuestion).input 与紧随的 tool_result。
既不认摘要、也不认我自己写的 note。
"""
import io
import json
import os
import re
import sys

ROOTS = [r'C:\Users\23002\.workbuddy\projects']
PAT = re.compile(u'门|door|spr_|bg_castle|ralsei|大小|尺寸', re.I)

rows = []


def walk(d):
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isdir(p):
            for q in walk(p):
                yield q
        elif name.endswith('.jsonl'):
            yield p


def txt_of(c):
    if isinstance(c, list):
        out = []
        for it in c:
            if isinstance(it, dict):
                out.append(it.get('text') or it.get('content') or '')
            else:
                out.append(str(it))
        return u'\n'.join(str(x) for x in out)
    return c if isinstance(c, str) else u''


for root in ROOTS:
    for p in walk(root):
        base = os.path.basename(p)
        with io.open(p, encoding='utf-8', errors='replace') as fh:
            for ln, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if not isinstance(o, dict):
                    continue
                if o.get('type') != 'message':
                    continue
                role = o.get('role')
                ts = o.get('timestamp')
                c = o.get('content')
                if role == 'assistant' and isinstance(c, list):
                    for it in c:
                        if not isinstance(it, dict):
                            continue
                        if it.get('type') == 'tool_use' and \
                                'AskUserQuestion' in str(it.get('name', '')):
                            q = json.dumps(it.get('input'), ensure_ascii=False)
                            if PAT.search(q):
                                rows.append((ts, base, ln, 'ASK', q))
                if role == 'user' and isinstance(c, list):
                    for it in c:
                        if not isinstance(it, dict):
                            continue
                        if it.get('type') == 'tool_result':
                            r = json.dumps(it.get('content'), ensure_ascii=False)
                            if PAT.search(r):
                                rows.append((ts, base, ln, 'ANS', r))

rows.sort(key=lambda r: (str(r[0]), r[2]))
print('AskUserQuestion 相关条目 = %d' % len(rows))
for ts, base, ln, kind, s in rows:
    print('=' * 76)
    print('%s  %s :%d  [%s]' % (ts, base[:20], ln, kind))
    print(s[:3000])
