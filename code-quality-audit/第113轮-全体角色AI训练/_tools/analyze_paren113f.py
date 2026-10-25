# -*- coding: utf-8 -*-
"""读 probe_paren113f.jsonl 出结论表 + 抽样原文。

★ 必须过滤 `errors>0` 的行：探针第一次跑时 `wait_for_memory` 写错模块，
  48 次调用全抛异常并被吞掉，四个变体齐刷刷 0.00（看着像「大家都很好」）；
  后来又有一个负控制故意打断 chat，往同一个文件写了 8 行垃圾。
  两批都是「夹具失效」，**不许进统计**。
"""
import io
import json
import os
import sys

ROUND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
P = os.path.join(ROUND, '_evidence', 'probe_paren113f.jsonl')

rows = []
bad = 0
for ln in io.open(P, encoding='utf-8'):
    ln = ln.strip()
    if not ln:
        continue
    try:
        r = json.loads(ln)
    except Exception:
        bad += 1
        continue
    s = r.get('summary') or {}
    if s.get('errors') or s.get('empty_turns') == s.get('turns'):
        bad += 1
        continue
    rows.append(r)

print('有效 %d 行 / 丢弃 %d 行（夹具失效）' % (len(rows), bad))
if not rows:
    print('!! 没有有效数据')
    sys.exit(2)

print('\n%-8s %-11s %-7s %-9s %-7s %-7s %s'
      % ('角色', '变体', '括号率', '括号轮数', '均长', '中文', '含引号括号'))
print('-' * 72)
for r in rows:
    s = r['summary']
    print('%-8s %-11s %5.2f   %d/%d      %6.1f   %5.2f   %d'
          % (s['id'], s['variant'], s['paren_rate'],
             s['paren_turns'], s['turns'], s['avg_chars'], s['avg_cn'],
             s['quoted_turns']))

print('\n===== 按变体汇总（跨角色）=====')
tot = {}
for r in rows:
    s = r['summary']
    d = tot.setdefault(s['variant'], {'p': 0, 'n': 0, 'q': 0})
    d['p'] += s['paren_turns']
    d['n'] += s['turns']
    d['q'] += s['quoted_turns']
for v in sorted(tot):
    d = tot[v]
    print('%-11s 括号 %2d/%2d = %.2f   含引号括号 %d'
          % (v, d['p'], d['n'], d['p'] / float(d['n']), d['q']))

print('\n===== 抽样原文（每变体第 1 轮，看语气有没有被规则削平）=====')
for r in rows:
    s = r['summary']
    if s['variant'] not in ('P0 base', 'P3 both'):
        continue
    t = r['turns'][0]
    print('\n[%s / %s]' % (s['id'], s['variant']))
    print('  ' + (t['text'] or '(空)').replace('\n', ' / ')[:200])
