# -*- coding: utf-8 -*-
"""第45轮 · 五章可达性 + 原作拓扑缺口取证（一次性工具，产物落 _evidence/）。

为什么要生成这个文件：寻路回归锁（verify_pathfind45.py）里 B7 断言
「ch4/ch5 从 krisroom 走不到教堂」，那是**如实报告**的设计律 1，不是 bug。
但"为什么走不到"必须有据可查 —— 本脚本把实测事实蒸馏进仓库，
免得日后有人以为锁写错了。

判据：**用房间图自己的 src_name/dst_name**（第42轮反汇编带出来的原始名），
不去猜场景名（产品场景名是派生的，`room_krisroom` 在索引里未必叫这个）。
"""
import io
import json
import os
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
GRAPH = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证',
                     '_evidence', '_room_graph.json')
OUT = os.path.join(HERE, '_evidence', '五章可达性实测45.txt')

with io.open(GRAPH, encoding='utf-8') as fh:
    doc = json.load(fh)

lines = []
lines.append('第45轮 · 五章可达性实测（数据源 = 第42轮 _room_graph.json，782 边）')
lines.append('=' * 68)
lines.append('')

for ch in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
    rec = doc['chapters'][ch]
    edges = rec['edges']
    # 建邻接 + 反查"哪个下标叫 room_krisroom"
    adj = {}
    name_of = {}
    for e in edges:
        adj.setdefault(e['src'], []).append(e)
        name_of[e['src']] = e.get('src_name') or name_of.get(e['src'])
        name_of.setdefault(e['dst'], e.get('dst_name') or '')
    room = {v: k for k, v in name_of.items()}
    start = room.get('room_krisroom')
    seen = set()
    if start is not None:
        q = deque([start]); seen = {start}
        while q:
            c = q.popleft()
            for e in adj.get(c) or []:
                if e['dst'] not in seen:
                    seen.add(e['dst']); q.append(e['dst'])
    lines.append('%s: n_edges=%d  room_krisroom=%r  krisroom 出度=%d  从 krisroom 可达房间数=%d'
                 % (ch, len(edges), start,
                    len(adj.get(start) or []) if start is not None else 0, len(seen)))

lines.append('')
lines.append('★ 缺口实证（ch4 缺 torhouse → town_krisyard 回程边）:')
for ch in ('ch4', 'ch5'):
    rec = doc['chapters'][ch]
    edges = rec['edges']
    name_of = {}
    for e in edges:
        name_of[e['src']] = e.get('src_name')
        name_of.setdefault(e['dst'], e.get('dst_name'))
    room = {v: k for k, v in name_of.items() if v}
    th, ky = room.get('room_torhouse'), room.get('room_town_krisyard')
    has = None
    if th is not None and ky is not None:
        has = any(e['dst'] == ky for e in edges if e['src'] == th)
    lines.append('  %s: room_torhouse=%r room_town_krisyard=%r  边存在? %s'
                 % (ch, th, ky, has))
lines.append('')
lines.append('结论：ch4 该边缺失（第42轮取证漏采，非代码 bug）⇒ ch4 从 krisroom')
lines.append('      只能走到 4 间房；ch5 room_krisroom 出边 = 0 ⇒ 只可达 1 间。')
lines.append('      寻路器**如实报告"走不到"**（设计律 1），不就近凑。')
lines.append('      修复 = 重跑 UTMT 补采（已列入待办）。')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(lines).rstrip() + '\n')
print('\n'.join(lines))
