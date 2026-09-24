# -*- coding: utf-8 -*-
"""第44轮续 · 「room 是否齐全 + 连接顺序是否对」复检（只读）。

对比两侧：
  原作侧 = E:\\Download\\_tmp\\drw\\chapter{1..5}_windows\\rooms44.json（UTMT 刚导出）
  产品侧 = ralsei_pet/assets/scenes/{_original_rooms.json, _index.json,
            _routes.json, _zone.*.json, <scene_id>.json}

三层判据：
  L1 房间表齐全：原作 Rooms 总数 vs _original_rooms.json 的 ch1..ch5 条目数
  L2 场景覆盖：原作每间房 → 产品是否有对应场景（room_id 反查）
  L3 连接顺序：原作 room 顺序单调性 + 产品路由的 priority/链完整性
"""
import io
import json
import os
import re
import sys
import collections

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
DRW = r'E:\Download\_tmp\drw'
CHS = ['chapter1_windows', 'chapter2_windows', 'chapter3_windows',
       'chapter4_windows', 'chapter5_windows']
TAG = {CHS[i]: 'ch%d' % (i + 1) for i in range(5)}


def jload(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


out = []


def P(s=''):
    out.append(s)
    print(s)


# ---------------------------------------------------------------- 原作侧
P('=' * 78)
P('[L1] 原作侧：UTMT 刚导出的 Rooms 全量')
orig_rooms = {}          # ch -> [(id, name, w, h, n_doors, n_markers)]
for w in CHS:
    p = os.path.join(DRW, w, 'rooms44.json')
    if not os.path.isfile(p):
        P('  [WARN] 缺 %s' % p)
        continue
    d = jload(p)
    ch = TAG[w]
    rs = d['rooms']
    orig_rooms[ch] = [(r['id'], r['name'], r['w'], r['h'],
                       len(r.get('doors') or []), len(r.get('markers') or []))
                      for r in rs]
    nd = sum(r[4] for r in orig_rooms[ch])
    nm = sum(r[5] for r in orig_rooms[ch])
    P('  %-5s Rooms=%-5d 门实例=%-4d 落点实例=%-5d' % (ch, len(rs), nd, nm))
tot_orig = sum(len(v) for v in orig_rooms.values())
P('  ---- 原作 Rooms 合计 = %d' % tot_orig)

# ---------------------------------------------------------------- 产品侧
P()
P('[L2] 产品侧：_original_rooms.json')
rop = jload(os.path.join(SC, '_original_rooms.json'))
prod_rooms = {}
for ch, v in sorted(rop['chapters'].items()):
    rr = v.get('rooms') or []
    prod_rooms[ch] = {int(r['id']): r.get('name') for r in rr}
    P('  %-5s 条目=%-5d  name=%s alias=%s'
      % (ch, len(rr), v.get('name'), v.get('display_alias')))
tot_prod = sum(len(v) for v in prod_rooms.values())
P('  ---- 产品房间表合计 = %d' % tot_prod)

P()
P('[L2b] 逐章：原作 Rooms 数 vs 产品房间表条目数（差 = 还原缺口）')
gap_total = 0
for ch in ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']:
    a = len(orig_rooms.get(ch, []))
    b = len(prod_rooms.get(ch, {}))
    gap = a - b
    gap_total += gap
    flag = 'OK' if gap == 0 else ('缺 %d' % gap if gap > 0 else '多 %d' % -gap)
    P('  %-5s 原作=%-5d 产品=%-5d  %s' % (ch, a, b, flag))
P('  ---- 合计缺口 = %d' % gap_total)

P()
P('[L2c] 原作有、产品缺的 room id（逐章列出，最多每章 30 个）')
miss_all = 0
for ch in ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']:
    a_ids = {r[0] for r in orig_rooms.get(ch, [])}
    b_ids = set(prod_rooms.get(ch, {}))
    miss = sorted(a_ids - b_ids)
    extra = sorted(b_ids - a_ids)
    miss_all += len(miss)
    P('  %-5s 缺=%d 多=%d' % (ch, len(miss), len(extra)))
    if miss:
        P('        缺: %s%s' % (miss[:30], ' ...' if len(miss) > 30 else ''))
    if extra:
        P('        多: %s%s' % (extra[:30], ' ...' if len(extra) > 30 else ''))
P('  ---- 总缺口 = %d' % miss_all)

# ---------------------------------------------------------------- 场景覆盖
P()
P('[L3] 场景覆盖：产品场景 ↔ 原作 room')
idx = jload(os.path.join(SC, '_index.json'))
chapters = idx.get('chapters') or {}

# 索引结构：chapters.<ch>.areas.<area>.scenes.<scene_id> = {name, file,
#             original_room_id, name_raw, ...}
scenes = {}                # scene_id -> entry（拍平）
scene_ch = {}              # scene_id -> chapter_id
for ch, cv in chapters.items():
    for area, av in (cv.get('areas') or {}).items():
        for sid, e in (av.get('scenes') or {}).items():
            scenes[sid] = dict(e)
            scenes[sid]['_chapter'] = ch
            scenes[sid]['_area'] = area

P('  索引登记场景数 = %d' % len(scenes))
P('  default_scene  = %s' % idx.get('default_scene'))
P('  各章场景数：%s'
  % {ch: sum(1 for s in scenes.values() if s['_chapter'] == ch)
     for ch in chapters})

# 独立文件 vs 分片：索引里带 file 的是独立文件；分片场景也要登记在索引里
n_file = sum(1 for e in scenes.values() if e.get('file'))
P('  带 file（独立文件）= %d ；无 file（住在分片）= %d'
  % (n_file, len(scenes) - n_file))

# room_id 覆盖（索引里叫 original_room_id）
rid_map = collections.defaultdict(set)     # ch -> {room_id}
n_with_room = 0
for sid, e in scenes.items():
    rid = e.get('original_room_id')
    if rid is not None:
        n_with_room += 1
        rid_map[e['_chapter']].add(int(rid))
P('  带 original_room_id 的场景 = %d / %d' % (n_with_room, len(scenes)))

covered = set()
for ch, s in rid_map.items():
    for r in s:
        covered.add((ch, r))

orig_all = set()
for ch in ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']:
    for r in orig_rooms.get(ch, []):
        orig_all.add((ch, r[0]))
P('  原作 (章,room) 对 = %d ；产品已覆盖 = %d ；未覆盖 = %d'
  % (len(orig_all), len(orig_all & covered), len(orig_all - covered)))
un = sorted(orig_all - covered)
P('  未覆盖样例（前 25）: %s' % un[:25])

# ---------------------------------------------------------------- 路由
P()
P('[L4] 路由表：连接顺序')
routes = jload(os.path.join(SC, '_routes.json'))
rl = routes.get('routes') or []
P('  规则数 = %d ；_fallback = %s'
  % (len(rl), json.dumps(routes.get('_fallback'), ensure_ascii=False)))
prios = [r.get('priority') for r in rl]
P('  priority 取值域 = %s' % sorted(set(prios), key=lambda x: (x is None, x)))
mono = all((prios[i] or 0) <= (prios[i + 1] or 0) for i in range(len(prios) - 1))
P('  priority 声明序单调不减 = %s' % mono)
tgt_missing = [r.get('to') for r in rl if r.get('to') not in scenes]
P('  目标场景未登记 = %d %s' % (len(tgt_missing), tgt_missing[:8]))
tos = {r.get('to') for r in rl if r.get('to')}
froms = {r.get('when_scene') for r in rl if r.get('when_scene')}
P('  to 集合=%d ；when_scene 集合=%d ；断链（to 无人接续）=%d'
  % (len(tos), len(froms), len(tos - froms)))
P('  断链点: %s' % sorted(tos - froms))
P()
P('  全部规则（按声明序）:')
for r in rl:
    P('    p=%-4s %-30s | when_scene=%-28s when_area=%-12s'
      % (r.get('priority'), r.get('to'), r.get('when_scene') or '-',
         r.get('when_area') or '-'))

# ---------------------------------------------------------------- 原作顺序
P()
P('[L5] 原作房间顺序（_original_rooms.json 的 order 字段语义）')
for ch in ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']:
    v = rop['chapters'][ch]
    P('  %-5s keys=%s' % (ch, sorted(v)))
    ar = v.get('areas')
    if isinstance(ar, dict):
        P('        areas=%d: %s' % (len(ar), sorted(ar)[:10]))
        k0 = sorted(ar)[0]
        P('        %s -> %s' % (k0, json.dumps(ar[k0], ensure_ascii=False)[:160]))

print()
print('[done] 复检数据已生成')
