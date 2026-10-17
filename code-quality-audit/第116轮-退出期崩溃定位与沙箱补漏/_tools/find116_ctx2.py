# -*- coding: utf-8 -*-
u"""导出第112轮窗口内**用户短消息**（含"门/框/任意"），按行号序（只读）。"""
import io
import json
import os

F = (r'C:\Users\23002\.workbuddy\projects'
     r'\c-Users-23002-WorkBuddy-Worktrees-try - 副本-main-a7556e9c'
     r'\09ab7acc-3691-452e-91e0-7bb809a36f5d.jsonl')
LO, HI = 24200, 26200
KEYS = [u'门', u'框', u'任意', u'ut ', u'王座']


def textof(o):
    m = o.get('message')
    if isinstance(m, dict):
        o = m
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
    return u''


for ln, line in enumerate(io.open(F, encoding='utf-8', errors='replace'), 1):
    if ln < LO or ln > HI:
        continue
    line = line.strip()
    if not line:
        continue
    try:
        o = json.loads(line)
    except Exception:
        continue
    t = textof(o)
    if not t or len(t) > 4000:
        continue
    if not any(k in t for k in KEYS):
        continue
    role = o.get('role') or (o.get('message') or {}).get('role')
    if role != 'user':
        continue
    print('=' * 76)
    print(':%d  len=%d' % (ln, len(t)))
    print(t[-1500:].replace('\r', ''))
