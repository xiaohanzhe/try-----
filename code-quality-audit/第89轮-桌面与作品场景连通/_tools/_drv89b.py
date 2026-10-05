# -*- coding: utf-8 -*-
import os, sys, time
PKG = 'C:\\Users\\23002\\Desktop\\项目文件夹\\try - 副本\\ralsei_pet'
for _p in (os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    sys.path.append(_p)
os.environ.pop('QT_QPA_PLATFORM', None)
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
try:
    import ctypes as _ct
    _ct.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
app = QApplication.instance() or QApplication([])
from main import RalseiPet
pet = RalseiPet()
pet.BEDTIME_ENABLED = False
pet._npc_roam_last_tick = float('inf')

TARGETS = ['ch1.castle_town.castle_town', 'uty.rooms.rm_intro', 'oneshot.barrens.Blue', 'desktop']
STEP_MS = 9000
_idx = [0]


def _dump(tag):
    out = ['[STATE] ' + tag]
    try:
        cam = pet.__dict__.get('_scene_camera')
        out.append('  cam=' + repr(None if cam is None else tuple(
            round(v, 1) for v in cam.rect) if cam.rect else 'rectNone'))
    except Exception as e:
        out.append('  cam EXC ' + repr(e))
    try:
        st = pet.__dict__.get('_scene_state')
        out.append('  state=' + repr(None if st is None else
                                        getattr(st, 'scene_id', st))[:80])
    except Exception as e:
        out.append('  state EXC ' + repr(e))
    try:
        cv = pet.__dict__.get('scene_canvas')
        if cv is None:
            out.append('  canvas=None')
        else:
            g = cv.frameGeometry() if hasattr(cv, 'frameGeometry') else None
            out.append('  canvas vis=' + repr(cv.isVisible())
                       + ' as_window=' + repr(getattr(cv, 'as_window', '?'))
                       + ' size=' + repr((cv.width(), cv.height()))
                       + ' geo=' + repr((g.x(), g.y(), g.width(),
                                         g.height()) if g else None)
                       + ' flags=' + repr(cv.windowFlags()))
    except Exception as e:
        out.append('  canvas EXC ' + repr(e))
    try:
        out.append('  layer_visible=' + repr(
            pet.__dict__.get('_scene_layer_visible')))
    except Exception:
        pass
    try:
        plan = pet.scene.plan_frame()
        kinds = {}
        for it in (plan or []):
            k = it.get('kind') if isinstance(it, dict) else '?'
            kinds[k] = kinds.get(k, 0) + 1
        out.append('  plan n=%d kinds=%r' % (len(plan or []), kinds))
        for it in (plan or []):
            if isinstance(it, dict) and it.get('kind') == 'bg':
                out.append('  bg name=%r rect=%r'
                           % (it.get('name'), it.get('rect')))
                break
    except Exception as e:
        out.append('  plan EXC ' + repr(e))
    print('\n'.join(out), flush=True)


def step():
    if _idx[0] >= len(TARGETS):
        print('[DRV] done', flush=True)
        app.quit()
        return
    t = TARGETS[_idx[0]]
    _idx[0] += 1
    try:
        r = pet.travel_to_scene(t)
        ok = r.get('ok') if isinstance(r, dict) else r
        sid = r.get('scene_id') if isinstance(r, dict) else None
        print('[DRV] travel_to_scene(' + repr(t) + ') ok=' + repr(ok)
              + ' sid=' + repr(sid)
              + ' now=' + repr(pet.__dict__.get('current_scene')), flush=True)
    except Exception as e:
        print('[DRV] EXC ' + repr(e), flush=True)
    # 让事件循环跑几帧，把相机/画布都养出来，再自报状态
    QTimer.singleShot(2500, lambda: _dump('after ' + repr(t)))
    QTimer.singleShot(STEP_MS, step)


QTimer.singleShot(4000, step)
QTimer.singleShot(4000 + STEP_MS * (len(TARGETS) + 1), app.quit)
app.exec_()
