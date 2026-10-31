# -*- coding: utf-8 -*-
u"""第126轮取证探针 C：outertale 的**门路由**可行性体检。

现有事实：outertale 244 个场景、产品 `_routes.json` 里 **0** 条（零边）。
第115轮 `conn115.json` 已有 outertale **144** 条可信边（GML `if (room == N) room_goto(M)`
的常量对，src 取自同一 code 内的守卫）。

本探针回答五个问题（只读）：
  ① outertale 场景在注册表里有多少、带 `original_room_id` 的有多少
  ② 144 条边里两端都能解析到场景的有多少（按 `original_room_id`，**不按名字**）
  ③ 去掉自环 / 三元重复 / 产品已有 之后还剩多少
  ④ 端点解析不到的边，是"房间没注册"还是"rid 缺失"
  ⑤ 已收 ut 段（第122/123轮）的路由形状，供 outertale 对齐
"""
import io
import os
import json
import collections
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')
EV115 = os.path.join(REPO, 'code-quality-audit', '第115轮-跨作品物件普查', '_evidence')
CONN = os.path.join(EV115, 'conn115.json')
for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from modules import scene_system as SS  # noqa: E402


def jload(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


IDX = SS.load_index(SCENES)
SCN = IDX.get('scenes') or {}
RL = (json.loads(io.open(ROUTES, encoding='utf-8', newline='').read()) or {}).get('routes') or []
D = jload(CONN)

ot = {sid: r for sid, r in SCN.items() if sid.startswith('outertale.')}
uty = {sid: r for sid, r in SCN.items() if sid.startswith('uty.')}
print(u'① 场景数：outertale %d · uty %d' % (len(ot), len(uty)))
ot_rid = {r.get('original_room_id'): sid for sid, r in ot.items()
          if isinstance(r.get('original_room_id'), int)}
print(u'   outertale 带 original_room_id：%d（去重后 %d）'
      % (sum(1 for r in ot.values() if isinstance(r.get('original_room_id'), int)), len(ot_rid)))
print(u'   outertale 无 rid 的场景：%d'
      % sum(1 for r in ot.values() if not isinstance(r.get('original_room_id'), int)))

by_prefix = collections.Counter(sid.split('.')[0] for sid in SCN)
print(u'   注册表按作品：%r' % dict(by_prefix))
print(u'   产品路由按作品：%r'
      % dict(collections.Counter((r.get('when_scene') or '?').split('.')[0] for r in RL)))

E = D['outertale']['edges']
print(u'')
print(u'② conn115 outertale 边：%d 条' % len(E))
ok = bad_src = bad_dst = self_loop = 0
missing_src, missing_dst = set(), set()
for e in E:
    s, d = ot_rid.get(e.get('src')), ot_rid.get(e.get('dst'))
    if s is None:
        bad_src += 1
        missing_src.add((e.get('src'), e.get('src_name')))
    if d is None:
        bad_dst += 1
        missing_dst.add((e.get('dst'), e.get('dst_name')))
    if s and d:
        if s == d:
            self_loop += 1
        else:
            ok += 1
print(u'   两端可解析 %d · src 缺 %d · dst 缺 %d · 自环 %d' % (ok, bad_src, bad_dst, self_loop))
print(u'   src 缺的房间：%r' % (sorted(missing_src)[:12],))
print(u'   dst 缺的房间：%r' % (sorted(missing_dst)[:12],))

have = set((r.get('when_scene'), r.get('to')) for r in RL)
have_door = set((r.get('when_scene'), str(r.get('when_door') or '')) for r in RL)
seen = collections.Counter()
trip = 0
dup = 0
plan = []
for e in E:
    s, d = ot_rid.get(e.get('src')), ot_rid.get(e.get('dst'))
    if not s or not d or s == d:
        continue
    k = (s, e.get('code'), d)
    trip += 1
    if seen[k]:
        dup += 1
        continue
    seen[k] += 1
    if (s, d) in have:
        continue
    plan.append({'src': s, 'dst': d, 'code': e.get('code'),
                 'src_name': e.get('src_name'), 'dst_name': e.get('dst_name'),
                 'src_rid': e.get('src'), 'dst_rid': e.get('dst')})

print(u'')
print(u'③ 去重账：两端可解析且非自环 %d → 三元去重后 %d（重复 %d）→ 去掉产品已有后 **%d** 条候选'
      % (ok, trip - dup, dup, len(plan)))
srcs = set(p['src'] for p in plan)
dsts = set(p['dst'] for p in plan)
print(u'   覆盖场景：src %d 个 / dst %d 个 / 并集 %d 个' % (len(srcs), len(dsts), len(srcs | dsts)))
print(u'   其中 src 已有 outgoing 路由的场景：%d'
      % sum(1 for s in srcs if any(a == s for a, _ in have)))

print(u'')
print(u'④ 已收 ut 段形状（对照）')
ut = [r for r in RL if (r.get('when_scene') or '').startswith('ut.')]
print(u'   ut 路由 %d 条 · priority 范围 %s'
      % (len(ut), (min(r['priority'] for r in ut), max(r['priority'] for r in ut)) if ut else None))
for r in ut[:2]:
    print(u'   ' + json.dumps(r, ensure_ascii=False)[:400])

print(u'')
print(u'⑤ 候选样例（前 8 条）')
for p in plan[:8]:
    print(u'   %-42s --%-34s--> %s' % (p['src'], p['code'], p['dst']))
print(u'   涉及 code 去重 %d 个' % len(set(p['code'] for p in plan)))
