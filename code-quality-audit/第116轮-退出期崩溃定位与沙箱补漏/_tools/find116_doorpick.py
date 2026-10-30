# -*- coding: utf-8 -*-
u"""★ 第116轮取证：用户到底**选了哪张门贴图**（逐字原话 + AskUserQuestion 问答对）。

为什么要单独写：第116轮一度把门 D 从 `spr_giantdarkdoor_0.png` **回退**成
`spr_shortcut_door_0.png`（理由来自一份会话摘要的转述）。**摘要不是原话**
—— 本项目铁律「判据别被别处喂饱」。本脚本只认两样东西：
  ① `role=user` 的**当场发言**（跳过 `conversation_history_summary` 等注入块）；
  ② `AskUserQuestion` 的**问题 + 用户选择**（tool_use 的 input + tool_result）。
两样都不含"我写的总结"。
"""
import io
import json
import os
import re

ROOTS = [r'C:\Users\23002\.workbuddy\projects']
KEY = [u'任意门', u'门框', u'门的形式', u'门都不是', u'门也不是', u'门把']
SPR = ['spr_shortcut_door', 'spr_giantdarkdoor', 'ut_castle_realdoor',
       'desk_door_ut', 'desk_door_deltarune', 'niko_door_portal', 'spr_darkdoor']

out = []


def walk(d):
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isdir(p):
            for q in walk(p):
                yield q
        elif name.endswith('.jsonl'):
            yield p


def _txt(c):
    if isinstance(c, list):
        parts = []
        for it in c:
            if isinstance(it, dict):
                parts.append(it.get('text') or '')
            else:
                parts.append(str(it))
        return u'\n'.join(parts)
    return c if isinstance(c, str) else u''


def want(t):
    return any(k in t for k in KEY) or any(s in t for s in SPR)


files = 0
lines = 0
for root in ROOTS:
    for p in walk(root):
        files += 1
        with io.open(p, encoding='utf-8', errors='replace') as fh:
            for ln, line in enumerate(fh, 1):
                lines += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if not isinstance(o, dict):
                    continue
                msg = o.get('message') if isinstance(o.get('message'), dict) else o
                role = msg.get('role')
                # --- ① 用户当场发言 ---
                if role == 'user':
                    c = _txt(msg.get('content'))
                    if not c or len(c) > 20000:
                        continue
                    if c.lstrip()[:80].startswith('<'):
                        continue
                    if 'conversation_history_summary' in c[:400]:
                        continue
                    if 'Please continue' in c[:80]:
                        continue
                    if want(c):
                        out.append((p, ln, 'USER', c))
                # --- ② AskUserQuestion（问题 + 用户选择） ---
                c = msg.get('content')
                if isinstance(c, list):
                    for it in c:
                        if not isinstance(it, dict):
                            continue
                        if it.get('type') == 'tool_use' and \
                                'AskUserQuestion' in str(it.get('name', '')):
                            s = json.dumps(it.get('input'), ensure_ascii=False)
                            if want(s):
                                out.append((p, ln, 'ASK-Q', s))
                        if it.get('type') == 'tool_result':
                            s = json.dumps(it.get('content'), ensure_ascii=False)
                            if want(s) and ('选择' in s or 'answer' in s.lower()
                                            or 'label' in s):
                                out.append((p, ln, 'ASK-A', s))

print('扫描 %d 个 jsonl / %d 行；命中 %d 条' % (files, lines, len(out)))
for p, ln, kind, txt in out:
    print('=' * 76)
    print('%s :%d  [%s]' % (os.path.basename(p), ln, kind))
    print(txt[:2600])
