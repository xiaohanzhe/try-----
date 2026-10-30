# -*- coding: utf-8 -*-
u"""★ 第116轮取证：所有 AskUserQuestion 的**问题/选项/用户答案**，按时间序（只读）。

jsonl 真结构（实测，勿臆测）：
  · `type='function_call'` 顶层带 `name` + `arguments`
  · 紧随 `type='function_call_result'`，其 `providerData.toolResult.content`
    就是用户点选项后回填的选择（形如「… 请问 UT 门用哪个？ → bg_castle_realdoor」）
"""
import io
import json
import os

ROOTS = [r'C:\Users\23002\.workbuddy\projects']
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
        recs = []
        with io.open(p, encoding='utf-8', errors='replace') as fh:
            for ln, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                if 'function_call' not in line and 'AskUserQuestion' not in line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if not isinstance(o, dict):
                    continue
                recs.append((ln, o))
        for i, (ln, o) in enumerate(recs):
            if o.get('type') != 'function_call':
                continue
            if 'AskUserQuestion' not in str(o.get('name', '')):
                continue
            try:
                args = json.loads(o.get('arguments') or '{}')
            except Exception:
                args = {}
            qs = args.get('questions') or []
            # 找紧随其后的结果
            ans = None
            for j in range(i + 1, min(i + 6, len(recs))):
                o2 = recs[j][1]
                if o2.get('type') == 'function_call_result':
                    tr = (o2.get('providerData') or {}).get('toolResult') or {}
                    ans = tr.get('content')
                    break
            rows.append((o.get('timestamp'), os.path.basename(p)[:16], ln,
                         qs, ans))

rows.sort(key=lambda r: (str(r[0]), r[2]))
print('AskUserQuestion = %d 次' % len(rows))
for ts, base, ln, qs, ans in rows:
    print('=' * 78)
    print('[%s] %s :%d' % (ts, base, ln))
    for q in qs:
        if not isinstance(q, dict):
            continue
        print('  Q: %s' % str(q.get('question'))[:400])
        for op in (q.get('options') or []):
            if isinstance(op, dict):
                print('     - %s :: %s' % (op.get('label'), op.get('description')))
    if ans:
        print('  A→ %s' % str(ans)[:1200].replace('\n', ' | '))
