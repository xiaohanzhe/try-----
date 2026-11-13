# -*- coding: utf-8 -*-
"""第186轮 · 产品层路由探针：拿真路由表 + 真 `route_for_door` 逐个门试。

不碰任何状态、只调纯函数（`route_for_door` / `classify` / `build_props` 的查表段）。
"""
import io
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
for p in (PKG, os.path.join(PKG, 'modules')):
    if p not in sys.path:
        sys.path.insert(0, p)

import item_interact as II          # noqa: E402
import scene_routing as SR          # noqa: E402
import scene_system as SS           # noqa: E402

routes = SR.load_routes()
print('routes ok=%s 条数=%d' % (routes.get('ok'), len(routes.get('routes') or [])))

CASES = [
    # (说明, 场景, 字母, src, pos, prev, 期望)
    ('maze_susie 下门 y=665', 'ch1.forest.forest_maze_susie', 'X', 'obj_doorX',
     [280, 665], None, 'ch1.forest.forest_before_maze'),
    ('maze_susie 上门 y=0', 'ch1.forest.forest_maze_susie', 'X', 'obj_doorX',
     [280, 0], None, 'ch1.forest.forest_maze2'),
    ('elev prev=牢廊', 'ch1.card_castle.cc_prisonelevator', 'X', 'obj_doorX_musfade',
     [280, 460], 'ch1.card_castle.card_castle_prison', 'ch1.card_castle.card_castle_prison'),
    ('elev prev=一层', 'ch1.card_castle.cc_prisonelevator', 'X', 'obj_doorX_musfade',
     [280, 460], 'ch1.card_castle.card_castle_1f', 'ch1.card_castle.card_castle_1f'),
    ('elev prev=五层', 'ch1.card_castle.cc_prisonelevator', 'X', 'obj_doorX_musfade',
     [280, 460], 'ch1.card_castle.card_castle_5f', 'ch1.card_castle.card_castle_5f'),
    ('elev prev=？？？', 'ch1.card_castle.cc_prisonelevator', 'X', 'obj_doorX_musfade',
     [280, 460], 'ch1.card_castle.card_castle_unknown', 'ch1.card_castle.card_castle_unknown'),
    ('elev 无来路 ⇒ 默认支', 'ch1.card_castle.cc_prisonelevator', 'X', 'obj_doorX_musfade',
     [280, 460], None, 'ch1.card_castle.card_castle_prison'),
    ('elev 陌生来路 ⇒ 默认支', 'ch1.card_castle.cc_prisonelevator', 'X', 'obj_doorX_musfade',
     [280, 460], 'ch1.hometown.diner', 'ch1.card_castle.card_castle_prison'),
    ('dark_chase2 滑行', 'ch1.dark_world.dark_chase2', None, 'obj_lancerslideevent',
     [280, 160], None, 'ch1.castle_town.castle_outskirts'),
    ('alphysclass B 门', 'ch1.hometown.alphysclass', 'B', 'obj_doorB',
     [242, 48], None, 'ch1.hometown.schoollobby'),
    ('cc_fountain 闭泉', 'ch1.card_castle.cc_fountain', None, 'obj_fountainkris',
     [300, 260], None, 'ch1.hometown.school_unusedroom'),
    ('新场景 D 门', 'ch1.hometown.school_unusedroom', 'D', 'obj_doorD',
     [140, 180], None, 'ch1.hometown.schooldoor'),
]

bad = 0
for name, sid, letter, src, pos, prev, want in CASES:
    got = II.route_for_door(routes, sid, letter, src=src, pos=pos, prev=prev)
    ok = got == want
    bad += 0 if ok else 1
    print('  %-26s %s  got=%s' % (name, 'OK ' if ok else 'BAD', got))

print('\n[分类]')
for n in ('obj_lancerslideevent', 'obj_fountainkris', 'obj_darkfountain', 'obj_doorB'):
    print('  %-24s %s' % (n, II.classify(n)))

print('\n[新场景可加载]')
idx = SS.load_index()
ent = (idx.get('scenes') or {}).get('ch1.hometown.school_unusedroom')
print('  索引登记:', bool(ent), ent and ent.get('original_room_id'))
sc = SS.load_scene('ch1.hometown.school_unusedroom', entry=ent)
print('  load_scene:', sc is not None,
      sc and sc.original_room_id, sc and len(sc.objects or []))
if sc:
    for o in sc.objects:
        print('     %-24s %s' % (o.get('src'), o.get('pos')))
print('  world_of_scene:', SS.world_of_scene(sc) if sc else None)

sys.exit(1 if bad else 0)
