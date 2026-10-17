# -*- coding: utf-8 -*-
u"""定位「那是不是任意门」这类**用户当场原话**所在行，打印其结构（只读）。"""
import io
import json
import os

root = r'C:\Users\23002\.workbuddy\projects'
NEEDLES = [u'那是不是任意门', u'我说的是那个门框', u'就是那个门框', u'王座那个门']


def textof(o):
    c = o.get('content')
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        out = []
        for it in c:
            if isinstance(it, dict):
                out.append(it.get('text') or it.get('content') or '')
            else:
                out.append(str(it))
        return u'\n'.join(out)
    m = o.get('message')
    if isinstance(m, dict):
        return textof(m)
    return u''


found = 0
for dp, dn, fn in os.walk(root):
    for name in fn:
        if not name.endswith('.jsonl'):
            continue
        p = os.path.join(dp, name)
        for ln, line in enumerate(io.open(p, encoding='utf-8', errors='replace'), 1):
            if not any(nd in line for nd in NEEDLES):
                continue
            line = line.strip()
            try:
                o = json.loads(line)
            except Exception:
                continue
            found += 1
            t = textof(o)
            role = o.get('role') or (o.get('message') or {}).get('role') \
                if isinstance(o.get('message'), dict) else o.get('role')
            print('=' * 76)
            print('FILE %s :%d  type=%r role=%r  textlen=%d'
                  % (os.path.basename(os.path.dirname(p)), ln,
                     o.get('type'), role, len(t)))
            # 只打印含关键词的**上下文片段**
            for nd in NEEDLES:
                i = t.find(nd)
                if i >= 0:
                    print('   ...%s...' % (t[max(0, i - 220):i + 220].replace('\n', ' | '),))
            if found > 25:
                raise SystemExit(0)
print('found=%d' % found)
