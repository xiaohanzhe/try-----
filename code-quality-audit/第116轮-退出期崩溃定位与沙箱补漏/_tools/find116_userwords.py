# -*- coding: utf-8 -*-
u"""在会话历史里找用户关于「门」的原话（只读）。"""
import io
import json
import os
import re

ROOTS = [r'C:\Users\23002\.workbuddy\projects']
PATS = [u'任意门', u'门框', u'门的形式', u'门也不是都长那样', u'门都不是']
HITS = []


def walk(d):
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isdir(p):
            for q in walk(p):          # ★ 必须 yield from；漏了 ⇒ 只扫到根目录
                yield q
        elif name.endswith('.jsonl'):
            yield p


def user_texts(path):
    with io.open(path, encoding='utf-8', errors='replace') as fh:
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
            role = o.get('role') or (o.get('message') or {}).get('role')
            if role != 'user':
                continue
            c = o.get('content') or (o.get('message') or {}).get('content')
            if isinstance(c, list):
                parts = []
                for it in c:
                    if isinstance(it, dict):
                        parts.append(it.get('text') or '')
                    else:
                        parts.append(str(it))
                c = u'\n'.join(parts)
            if not isinstance(c, str):
                continue
            if c.startswith('<') and 'system-reminder' in c[:200]:
                pass
            yield ln, c


for root in ROOTS:
    for p in walk(root):
        for ln, txt in user_texts(p):
            if len(txt) > 20000:
                continue
            # ★ 跳过"总结/系统注入"这类**不是用户当场说的话**的块
            #   （`conversation_history_summary` 里会**转述**用户口径，
            #    混进来会把"我写的总结"当成"用户的原话"—— 正是本项目
            #    已经踩过的"判据被别处喂饱"。）
            head = txt.lstrip()[:80]
            if head.startswith('<') or 'conversation_history_summary' in txt[:400]:
                continue
            if txt.strip().startswith('Please continue'):
                continue
            for pat in PATS:
                if pat in txt:
                    HITS.append((p, ln, pat, txt))
                    break

print('hits=%d' % len(HITS))
for p, ln, pat, txt in HITS:
    print('=' * 72)
    print('%s :%d  [%s]' % (os.path.basename(os.path.dirname(p)), ln, pat))
    print(repr(txt)[:1400])
