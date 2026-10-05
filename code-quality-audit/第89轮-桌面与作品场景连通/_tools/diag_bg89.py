# -*- coding: utf-8 -*-
u"""第89轮诊断：`plan_frame` 里 bg 指令的真实内容（为什么 Deltarune 画成灰网）。

★ 背景：真机抓图显示 `ch1.castle_town.castle_town` 的画布是**灰底斜网格**，
  而 `oneshot.barrens.Blue` 是**真实砖墙贴图**。
  数据层已证 `SceneState.bg == 'bg/ch1_castle_town_castle_town.png'` 且文件在盘，
  ⇒ 问题在**渲染计划**或**素材缓存**这一侧。
  本探针把两侧都摊开：
    ① `plan_frame` 里 `kind=='bg'` 的条目（rect / name / scale）；
    ② `SceneAssetCache.get(name)` 真取一次（拿到就是拿到、拿不到就记 missing）。
"""
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
for _p in (os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    sys.path.append(_p)

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(
    os.environ.get('TEMP', '.'), 'ralsei_dbg89c')

from PyQt5.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])

from main import RalseiPet  # noqa: E402
from scene_canvas import SceneAssetCache  # noqa: E402

pet = RalseiPet()
pet.BEDTIME_ENABLED = False
pet._npc_roam_last_tick = float('inf')

cache = SceneAssetCache()
print('SceneAssetCache.base =', cache.base)
print('  exists =', os.path.isdir(cache.base))

TARGETS = ['desktop', 'ch1.castle_town.castle_town',
           'oneshot.barrens.Blue', 'uty.rooms.rm_intro']
for t in TARGETS:
    print('\n' + '=' * 62)
    print('目标:', t)
    r = pet.scene.travel_to(t)
    print('  travel ok=%s now=%r' % (r.get('ok'), pet.__dict__.get('current_scene')))
    st = pet.__dict__.get('_scene_state')
    if st is None:
        print('  _scene_state = None')
        continue
    print('  bg        = %r' % getattr(st, 'bg', None))
    print('  room_id   = %r' % getattr(st, 'original_room_id', None))
    print('  chapter   = %r' % getattr(st, 'chapter_id', None))
    # ★ 真机才会走 update_movement（相机在里面 follow）；探针显式驱动一次
    try:
        pet.update_movement()
    except Exception as _e:
        print('  update_movement 异常:', repr(_e)[:80])
    cam = pet.__dict__.get('_scene_camera')
    print('  camera    = %s rect=%r' % (type(cam).__name__ if cam else None,
                                        getattr(cam, 'rect', None)))
    # 真算一次计划
    plan = pet.scene.plan_frame(tick=0, sprite_size=cache.sprite_size
                               if hasattr(cache, 'sprite_size') else None)
    print('  plan n    = %d' % len(plan))
    kinds = {}
    for it in plan:
        kinds[it.get('kind')] = kinds.get(it.get('kind'), 0) + 1
    print('  kinds     = %r' % kinds)
    for it in plan:
        if it.get('kind') == 'bg':
            nm = it.get('name')
            pm = cache.get(nm)
            print('  BG 指令: name=%r rect=%r' % (nm, it.get('rect')))
            print('     cache.get -> %s' % ('None(MISS)' if pm is None
                                            else '%dx%d OK' % (pm.width(), pm.height())))
            break
    else:
        print('  **没有任何 bg 指令**（⇒ 画布不会有背景，只有物件/占位）')
