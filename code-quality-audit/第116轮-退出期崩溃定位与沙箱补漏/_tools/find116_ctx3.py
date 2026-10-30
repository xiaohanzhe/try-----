# -*- coding: utf-8 -*-
u"""导出第112轮 AskUserQuestion 的问与答（只看工具调用/结果里含门框/giantdarkdoor 的）。"""
import io
import json

F = (r'C:\Users\23002\.workbuddy\projects'
     r'\c-Users-23002-WorkBuddy-Worktrees-try - 副本-main-a7556e9c'
     r'\09ab7acc-3691-452e-91e0-7bb809a36f5d.jsonl')
LO, HI = 24300, 26600
NEEDLES = [u'门框', u'giantdarkdoor', u'任意门', u'王座', u'AskUserQuestion']


def dump(o):
    parts = []
    for k in ('content', 'arguments', 'result', 'message'):
        v = o.get(k)
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            for it in v:
                if isinstance(it, dict):
                    parts.append(json.dumps(it, ensure_ascii=False))
                else:
                    parts.append(str(it))
        elif isinstance(v, dict):
            parts.append(json.dumps(v, ensure_ascii=False))
    return u'\n'.join(parts)


for ln, line in enumerate(io.open(F, encoding='utf-8', errors='replace'), 1):
    if ln < LO or ln > HI:
        continue
    line = line.strip()
    if not line:
        continue
    if not any(nd in line for nd in NEEDLES):
        continue
    try:
        o = json.loads(line)
    except Exception:
        continue
    t = dump(o)
    if not t:
        continue
    if u'门框' not in t and u'giantdarkdoor' not in t and u'任意门' not in t:
        continue
    print('=' * 76)
    print(':%d type=%r role=%r len=%d' % (ln, o.get('type'), o.get('role'), len(t)))
    print(t[:2600].replace('\r', ''))
