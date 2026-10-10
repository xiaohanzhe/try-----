# -*- coding: utf-8 -*-
u"""precheck105_route.py —— 录屏**之前**的一次纯数据面预检（不改任何东西）。

目的：先把"我要录的那条路线到底成不成立"用**产品自己的代码**问清楚，
      免得录了半天发现走不到（那是夹具设计错，不是产品缺陷 —— 记忆里
      「夹具不保真=报假问题」那条）。

跑法：
    cd <仓库根>
    C:\\Python311\\python.exe code-quality-audit\\第105轮-OneShot房间连接\\_tools\\precheck105_route.py
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MOD)

import scene_pathfind as SP                                            # noqa: E402
import scene_system as SS                                              # noqa: E402


def rj(p):
    return json.loads(io.open(p, encoding='utf-8', newline='').read())


IDX = SS.load_index()
# ★ 必须走 `load_room_graph()`（它把 `chapters.*.edges` 摊成 `edges_by_chapter`）；
#   直接把 JSON 顶层喂给 `plan_from_text` 会被判「edges_by_chapter 不是 dict」
#   —— 这正是"夹具不保真"的典型形状，先在预检里撞掉，别留到录屏。
GRAPH = SP.load_room_graph()
ALIASES = SP.load_aliases().get('entries') or {}


def plan(cur, tgt):
    return SP.plan_from_text(tgt, IDX, GRAPH, ALIASES, current_scene_id=cur)


print('=' * 78)
print(u'第105轮 · 录屏前路线预检（产品代码直算，不看录像也先确认真假）')
print('=' * 78)
print(u'场景索引 %d 间 / 房间图 %d 章 / 共 %d 边'
      % (len(IDX['scenes']), len(GRAPH['edges_by_chapter']), GRAPH.get('n_edges') or 0))
print(u'  分章边数：%s' % {k: len(v) for k, v in sorted(GRAPH['edges_by_chapter'].items())})

CASES = [
    ('oneshot.mainline.INIT', 'oneshot.mainline.S1', u'★ 主用例：跨 18 跳'),
    ('oneshot.mainline.INIT', 'oneshot.mainline.Start', u'单跳'),
    ('ch1.kris_room.kris_s_room', u'\u6559\u5802', u'既有 Deltarune 对照（ch1 到教堂）'),
]

BAD = 0
for cur, tgt, tag in CASES:
    p = plan(cur, tgt)
    print('-' * 78)
    print(u'[%s]  %s  →  %s' % (tag, cur, tgt))
    print(u'  ok=%r hops=%r scene_id=%r err=%r'
          % (p.get('ok'), p.get('hops'), p.get('scene_id'), p.get('error')))
    steps = p.get('steps') or []
    for i, s in enumerate(steps[:6], 1):
        print(u'   %2d. %-32s → %-32s door=%-14s %s'
              % (i, s.get('from'), s.get('to'), s.get('door'), s.get('reason')))
    if len(steps) > 6:
        print(u'   ...（共 %d 步，此处只印前 6）' % len(steps))
    if not p.get('ok'):
        BAD += 1
print('=' * 78)
# ★ 判据面向的是"夹具是否成立"：主用例必须 ok
main = plan('oneshot.mainline.INIT', 'oneshot.mainline.S1')
ok_main = bool(main.get('ok')) and (main.get('hops') or 0) > 1
print(u'主用例（INIT → S1）多跳成立 : %s' % (u'PASS' if ok_main else u'FAIL'))
if not ok_main:
    BAD += 1
sys.exit(1 if BAD else 0)
