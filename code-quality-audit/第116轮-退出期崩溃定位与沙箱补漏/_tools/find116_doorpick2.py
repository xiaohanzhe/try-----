# -*- coding: utf-8 -*-
u"""直接扫：所有 user 消息里含「门」的（只读）。带结构自证。"""
import io
import json
import os

ROOTS = [r'C:\Users\23002\.workbuddy\projects']
out = []
nfiles = 0
nmsg = 0
nuser = 0
roles = {}


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
        nfiles += 1
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
                nmsg += 1
                role = o.get('role')
                roles[role] = roles.get(role, 0) + 1
                if role != 'user':
                    continue
                nuser += 1
                c = o.get('content')
                if isinstance(c, list):
                    parts = []
                    for it in c:
                        if isinstance(it, dict):
                            parts.append(it.get('text') or '')
                        else:
                            parts.append(str(it))
                    c = u'\n'.join(parts)
                if not isinstance(c, str):
                    c = u''
                if u'门' in c and len(c) < 30000:
                    out.append((p, ln, c))

print('files=%d  message=%d  user=%d  roles=%r' % (nfiles, nmsg, nuser, roles))
print('含「门」的 user 消息 = %d 条' % len(out))
for p, ln, c in out:
    print('=' * 76)
    print('%s :%d' % (os.path.basename(p), ln))
    print(c[:1500])
