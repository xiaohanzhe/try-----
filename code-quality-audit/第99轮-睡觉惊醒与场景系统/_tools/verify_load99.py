# -*- coding: utf-8 -*-
u"""verify_load99.py —— 第99轮：outertale 数据面**真装载**验证。

不是"文件在盘上"，而是走产品**唯一入口** `scene_system.load_index()` /
`load_scene(sid, entry=)` / `item_interact.route_for_door()` 真读一遍。

★ 纪律：每条 print `[PASS] ` / `[FAIL] ` 字面量；负控制成对；不联网。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.normpath(os.path.join(ROUND, u'..', u'..'))
PET = os.path.join(ROOT, u'ralsei_pet')
SCENES = os.path.join(PET, u'assets', u'scenes')
sys.path.insert(0, PET)
sys.path.insert(0, os.path.join(PET, u'modules'))  # `item_interact` 顶层 import `companion`

from modules import scene_system as SYS          # noqa: E402
from modules import item_interact as II          # noqa: E402

CH = u'outertale'
FIRST = u'outertale.wastelands.w_start'
REGIONS = [u'wastelands', u'starton', u'foundry', u'aerialis', u'core',
           u'citadel', u'special']
NPASS = [0]
NFAIL = [0]


def ck(desc, cond, detail=u''):
    if cond:
        NPASS[0] += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        NFAIL[0] += 1
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


def rd(name):
    with io.open(os.path.join(SCENES, name), 'rb') as fh:
        return json.loads(fh.read().decode('utf-8'))


print(u'== A. 产品入口 load_index() ==')
idx = SYS.load_index()
ck(u'A1 load_index() 可用（ok=True）', idx.get(u'ok'),
   u'error=%r' % idx.get(u'error'))
chs = idx.get(u'chapters') or {}
ck(u'A2 章节数 == 10（原 9 + outertale）', len(chs) == 10,
   u'实得 %d：%s' % (len(chs), list(chs)))
ck(u'A3 新章 `outertale` 在索引里', CH in chs)
o = chs.get(CH) or {}
ck(u'A4 order == 103（接在 oneshot 102 之后）', o.get(u'order') == 103,
   u'order=%r alias=%r' % (o.get(u'order'), o.get(u'alias')))

flat = idx.get(u'scenes') or {}
mine = {k: v for k, v in flat.items() if k.startswith(CH + u'.')}
ck(u'A5 展平场景里 outertale.* == 244', len(mine) == 244, u'实得 %d' % len(mine))

# 与分片文件对账（单一真源交叉）
shard_total = 0
for rg in REGIONS:
    p = os.path.join(SCENES, u'_zone.%s.%s.json' % (CH, rg))
    if os.path.isfile(p):
        shard_total += len(rd(u'_zone.%s.%s.json' % (CH, rg))[u'scenes'])
ck(u'A6 七个分片房间数之和 == 索引展平数', shard_total == len(mine),
   u'分片 %d vs 索引 %d' % (shard_total, len(mine)))

print()
print(u'== B. load_scene() 真加载（每个区域抽 1 个 + 首场景）==')
probe = [FIRST]
for rg in REGIONS:
    cand = sorted(k for k in mine if k.split(u'.')[1] == rg)
    if cand and cand[0] not in probe:
        probe.append(cand[0])
ok = 0
for sid in probe:
    sc = SYS.load_scene(sid, entry=flat.get(sid))
    if sc is not None and getattr(sc, u'original_room_id', None) is not None:
        ok += 1
        print(u'    %-42s oid=%-5s name=%s'
              % (sid, sc.original_room_id, getattr(sc, u'name', u'')))
    else:
        print(u'    %-42s **加载失败 / 无 room_id**' % sid)
ck(u'B1 抽取的每个场景都能真加载且带 original_room_id', ok == len(probe),
   u'%d/%d' % (ok, len(probe)))

sc = SYS.load_scene(FIRST, entry=flat.get(FIRST))
ck(u'B2 ★ 首场景 `%s` 真加载成功' % FIRST, sc is not None)
ck(u'B2b ★ 不带 entry 时必须为 None（证明它真来自分片，不是独立文件）',
   SYS.load_scene(FIRST) is None)

print()
print(u'== C. 负控制（判据有鉴别力）==')
ck(u'C1 不存在的 outertale 场景 -> None',
   SYS.load_scene(u'outertale.wastelands.__no_such_room__',
                  entry={u'chapter_id': CH, u'area_id': u'wastelands'}) is None)
ck(u'C2 不存在的章 -> None',
   SYS.load_scene(u'outertale.__no_area__.x',
                  entry={u'chapter_id': CH, u'area_id': u'__no_area__'}) is None)
ck(u'C3 负控制：把章节 id 改错也必须失败（不是"随便给个 entry 就放行"）',
   SYS.load_scene(FIRST, entry={u'chapter_id': u'ut',
                                u'area_id': u'wastelands',
                                u'original_room_id': 0}) is None)

print()
print(u'== D. 桌面第 %s 号门 -> outertale（产品路由函数）==' % II.__dict__.get(u'X', u'Y'))
routes = rd(u'_routes.json')
ck(u'D1 `door_letter_of("obj_doorY")` == "Y"',
   II.door_letter_of(u'obj_doorY') == u'Y',
   u'实得 %r（DOOR_LETTERS=%r）' % (II.door_letter_of(u'obj_doorY'),
                                    II.DOOR_LETTERS))
ck(u'D2 桌面 Y 号门解析到 outertale 首场景',
   II.route_for_door(routes, u'desktop', u'Y') == FIRST,
   u'实得 %r' % II.route_for_door(routes, u'desktop', u'Y'))
ck(u'D2b 负控制：同一张表里查一个不存在的 YY 门 -> None',
   II.route_for_door(routes, u'desktop', u'YY') is None)
desk = [r for r in routes[u'routes'] if r.get(u'when_scene') == u'desktop']
ck(u'D3 桌面传送门条数 == 9（原 8 + outertale）', len(desk) == 9,
   u'实得 %d，门字母 %s' % (len(desk), sorted(r.get(u'when_door') for r in desk)))

print()
print(u'== E. 明暗表 / 几何缺口（如实登记）==')
wl = rd(u'_worlds.json')
ck(u'E1 _worlds.areas[outertale] 有 7 个区域且全 unknown',
   len(wl[u'areas'].get(CH) or {}) == 7
   and set((wl[u'areas'][CH]).values()) == {u'unknown'},
   u'%r' % (wl[u'areas'].get(CH),))
ck(u'E2 _worlds.rooms[outertale] 有 244 条且全 unknown',
   len(wl[u'rooms'].get(CH) or {}) == 244
   and set((wl[u'rooms'][CH]).values()) == {u'unknown'})
ur = [x for x in (wl[u'meta'].get(u'unknown_rooms') or [])
      if x.get(u'chapter') == CH]
ck(u'E3 meta.unknown_rooms 里 outertale 条目 == 244', len(ur) == 244,
   u'实得 %d' % len(ur))

rg = rd(u'_room_geometry.json')
gaps = rg.get(u'gaps') or {}
ck(u'E4 _room_geometry 登记了 outertale 缺口（不伪造尺寸）',
   (gaps.get(CH) or {}).get(u'rooms') == 244,
   u'%r' % ({k: v.get(u'rooms') for k, v in gaps.items()},))
hit = sum(1 for k in mine if (u'%s:%s' % (CH, flat[k].get(u'original_room_id')))
          in rg[u'rooms'])
miss = len(mine) - hit
ck(u'E5 ★ 几何未命中数 == 缺口登记数（判据与登记对账）',
   miss == (gaps.get(CH) or {}).get(u'rooms'),
   u'未命中 %d vs 登记 %r' % (miss, (gaps.get(CH) or {}).get(u'rooms')))

print()
print(u'[verify_load99] 结果：PASS=%d FAIL=%d' % (NPASS[0], NFAIL[0]))
sys.exit(0 if NFAIL[0] == 0 else 1)
