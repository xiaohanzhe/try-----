# -*- coding: utf-8 -*-
"""第44轮续 · priority 回绕缺陷量化（只读）。

发现：gen_routes44.py 用 `priority = 110 + (order % 240)`，order 是**全局**
计数器。当 order>240 回绕时，同一场景的出边 priority 不再随字母单调 —— 
破坏「没指定门时默认走字母最靠前的门」这条设计约定。

本脚本量化：有多少个多出边场景的「字母最靠前的门」不是 priority 最小者。
"""
import io
import json
import os
import collections

SC = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\assets\scenes'
with io.open(os.path.join(SC, '_routes.json'), encoding='utf-8') as fh:
    rd = json.load(fh)
routes = rd.get('routes') or []

by_src = collections.defaultdict(list)
for r in routes:
    by_src[r.get('when_scene')].append(r)

multi = {k: v for k, v in by_src.items() if len(v) > 1}
print('多出边场景 = %d' % len(multi))

bad = []
for k, v in sorted(multi.items()):
    v2 = sorted(v, key=lambda r: r.get('priority'))
    letters_in_priority_order = [r.get('when_door') for r in v2]
    letters_sorted = sorted(letters_in_priority_order)
    if letters_in_priority_order != letters_sorted:
        bad.append((k, letters_in_priority_order, [r.get('priority') for r in v2]))

print('「按 priority 取默认门」≠「字母最靠前」的场景 = %d' % len(bad))
for k, ls, ps in bad:
    print('  %s' % k)
    print('     priority序 -> %s' % list(zip(ls, ps)))
    print('     期望字母序 -> %s' % sorted(ls))

print()
print('==== 全表 priority 回绕统计 ====')
prios = [r.get('priority') for r in routes]
drops = [(i, prios[i-1], prios[i]) for i in range(1, len(prios))
         if prios[i] < prios[i-1]]
print('回绕次数 = %d' % len(drops))
print('回绕点前 3:', drops[:3])
print('末条 priority =', prios[-1], '；总条数 =', len(prios))
print('priority 值域 = [%d, %d]' % (min(prios), max(prios)))

# 受影响范围：order>=240 的规则条数
print()
print('order 计数器超过 240 的规则条数 = %d / %d'
      % (len(prios) - 240, len(prios)))
