# -*- coding: utf-8 -*-
u"""第93轮 P0-1 现场诊断：**为什么画布不可见 / 为什么换场景失败**。

不猜、只看事实：起真宠 → 4s 后 dump 场景系统全部内部状态（`current_scene` /
`_scene_state` / 相机 / `_scene_geometry` / `plan_frame` 的 kind 分布 / 画布几何）
→ 再依次试 `travel_to` / `switch`，把**完整返回 dict**打出来（含 `error` /
`ambiguous` / `candidates`），最后 dump 一次。

★ 只读诊断：不改任何产品代码，不依赖离屏平台（真窗口，语义与用户看到的一致）。
"""
import collections
import os
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
for _p in (os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    sys.path.append(_p)
os.environ.pop('QT_QPA_PLATFORM', None)
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(os.environ.get('TEMP', '.'), 'ralsei_diag93')

from PyQt5.QtCore import QTimer                     # noqa: E402
from PyQt5.QtWidgets import QApplication            # noqa: E402

app = QApplication.instance() or QApplication([])
from main import RalseiPet                          # noqa: E402

pet = RalseiPet()
pet.BEDTIME_ENABLED = False
pet._npc_roam_last_tick = float('inf')


def P(*a):
    print('[D] ' + ' '.join(str(x) for x in a), flush=True)


def dump(tag):
    P('=' * 12, tag, '=' * 12)
    P('current_scene =', repr(pet.__dict__.get('current_scene')))
    st = pet.__dict__.get('_scene_state')
    if st is None:
        P('_scene_state = None')
    else:
        d = {k: v for k, v in vars(st).items()} if hasattr(st, '__dict__') else {}
        P('_scene_state =', type(st).__name__, d)
    cam = pet.__dict__.get('_scene_camera')
    try:
        P('camera =', cam.describe() if cam else None,
          'scoped =', cam.scoped_size() if cam else None)
    except Exception as e:
        P('camera EXC', repr(e))
    geo = pet.__dict__.get('_scene_geometry') or {}
    P('geometry n =', len(geo), 'keys[:6] =', list(geo.keys())[:6])
    sc = pet.__dict__.get('scene')
    if sc is not None:
        try:
            P('scene.ready() =', sc.ready())
        except Exception as e:
            P('scene.ready EXC', repr(e))
        try:
            P('plan_viewport =', sc.plan_viewport())
        except Exception as e:
            P('plan_viewport EXC', repr(e))
        try:
            pl = sc.plan_frame(tick=int(time.time() * 1000))
            P('plan n =', len(pl))
            P('plan kinds =', dict(collections.Counter(it.get('kind') for it in pl)))
            P('plan head =', [(it.get('kind'), it.get('name') or it.get('id') or it.get('sprite'))
                              for it in pl[:8]])
        except Exception as e:
            P('plan_frame EXC', repr(e))
    cv = pet.__dict__.get('scene_canvas')
    if cv is not None:
        P('canvas visible =', cv.isVisible(), 'isWindow =', cv.isWindow(),
          'geo =', (cv.x(), cv.y(), cv.width(), cv.height()),
          'plan_n =', len(cv.plan()), 'view_size =', cv.view_size())
    P('SCENE_LAYER_ENABLED =', getattr(pet, 'SCENE_LAYER_ENABLED', None))


def try_travel(t):
    sc = pet.__dict__.get('scene')
    try:
        rv = sc.travel_to(t)
    except Exception as e:
        rv = {'EXC': repr(e)}
    P('travel_to(%r) ->' % t, rv)
    return rv


STEP = [0]


def step():
    sc = pet.__dict__.get('scene')
    if STEP[0] == 0:
        dump('idle 4s')
        if sc is not None:
            try:
                av = sc.available_scenes()
                P('available_scenes n =', len(av), 'head =', list(av)[:14])
            except Exception as e:
                P('available_scenes EXC', repr(e))
            try:
                P('destinations_text =', repr(sc.destinations_text())[:500])
            except Exception as e:
                P('destinations_text EXC', repr(e))
    elif STEP[0] == 1:
        try_travel('ch1.castle_town.castle_town')
        dump('after travel ch1')
    elif STEP[0] == 2:
        try_travel('desktop')
        if sc is not None:
            try:
                P('switch("desktop") ->', sc.switch('desktop'))
            except Exception as e:
                P('switch EXC', repr(e))
        dump('after travel desktop')
    elif STEP[0] == 3:
        dump('final')
        app.quit()
        return
    STEP[0] += 1
    QTimer.singleShot(4000, step)


QTimer.singleShot(4000, step)
QTimer.singleShot(60000, app.quit)
app.exec_()
