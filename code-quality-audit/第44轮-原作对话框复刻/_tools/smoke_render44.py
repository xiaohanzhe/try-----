# -*- coding: utf-8 -*-
"""第44轮 · 渲染链真机冒烟（真实数据，不是夹具）。

跑这条链：_index.json → load_scene → Camera.follow → plan_frame
用**真实数据**（第 43/44 轮的铁律：行为判据必须用真实量级输入）。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MOD)

import scene_system as SS      # noqa: E402
import scene_camera as SC      # noqa: E402
import scene_render as SR      # noqa: E402

SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')

idx = SS.load_index()
print('索引 ok =', idx.get('ok'), '场景数 =', len(idx.get('scenes') or {}))
geo = json.load(open(os.path.join(SCENES, '_room_geometry.json'), encoding='utf-8'))['rooms']
print('几何表 =', len(geo))

cases = ['ch1.kris_room.kris_s_room', 'desktop', 'ch1.castle_town.castle_town']
for sid in cases:
    ent = (idx.get('scenes') or {}).get(sid)
    if ent is None:
        print('  [SKIP] %s 未登记' % sid)
        continue
    scene = SS.load_scene(sid, entry=ent)
    if scene is None:
        print('  [SKIP] %s 加载失败' % sid)
        continue
    oid = getattr(scene, 'original_room_id', None)
    g = SR.room_geometry(oid, scene.chapter_id, geo)
    world = SR.room_world_rect(g, None)
    cam = SC.Camera((640, 480), 0, 1.5)
    tgt = (world[0] + world[2] / 2.0 - 8, world[1] + world[3] / 2.0 - 16,
           world[0] + world[2] / 2.0 + 8, world[1] + world[3] / 2.0)
    rect = cam.follow(world, tgt)
    plan = SR.plan_frame(scene, cam, geo)
    print('  %s  oid=%s geo=%s world=%s' % (sid, oid, g, world))
    print('      camera=%s  plan=%s' % (rect, SR.plan_summary(plan)))
    for it in plan[:4]:
        print('        ', it)
