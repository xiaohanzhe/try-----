# -*- coding: utf-8 -*-
"""第186轮 · 端到端探针：5 间房跑真 `build_props()`，看门有没有真被建出来、通向哪。"""
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
idx = SS.load_index()
scenes = idx.get('scenes') or {}

CASES = [
    ('ch1.forest.forest_maze_susie', None),
    ('ch1.card_castle.cc_prisonelevator', 'ch1.card_castle.card_castle_1f'),
    ('ch1.card_castle.cc_prisonelevator', None),
    ('ch1.dark_world.dark_chase2', None),
    ('ch1.hometown.alphysclass', None),
    ('ch1.card_castle.cc_fountain', None),
    ('ch1.hometown.school_unusedroom', None),
]

bad = 0
for sid, prev in CASES:
    ent = scenes.get(sid)
    sc = SS.load_scene(sid, entry=ent)
    if sc is None:
        print('!! %s 加载失败' % sid)
        bad += 1
        continue
    props = II.build_props(sc, 'ch1', 'dark', routes=routes, prev=prev,
                           on_enter=lambda t, d=None: True)
    doors = [p for p in props if getattr(p, 'kind', '') == 'door']
    print('\n=== %s  prev=%s  物件 %d / 门 %d ===' % (sid, prev, len(props), len(doors)))
    for p in props:
        tg = getattr(p, 'target_scene', None)
        print('   %-10s %-24s -> %s' % (getattr(p, 'kind', '?'), p.src, tg))
    if not doors:
        print('   [BAD] 一扇门都没建出来')
        bad += 1

print('\n门总数账：%d 个 BAD' % bad)
sys.exit(1 if bad else 0)
