# -*- coding: utf-8 -*-
import os, sys
PKG = 'C:\\Users\\23002\\Desktop\\项目文件夹\\try - 副本\\ralsei_pet'
for _p in (os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    sys.path.append(_p)
os.environ.pop('QT_QPA_PLATFORM', None)
import ctypes as _ct
try:
    _ct.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
app = QApplication.instance() or QApplication([])
from main import RalseiPet
pet = RalseiPet()
pet.BEDTIME_ENABLED = False
pet._npc_roam_last_tick = float('inf')


def go():
    for t in ('ch1.castle_town.castle_town', 'uty.rooms.rm_intro',
              'oneshot.barrens.Blue'):
        print('\n===== ' + t + ' =====', flush=True)
        try:
            pet.travel_to_scene(t)
        except Exception as e:
            print('  travel EXC ' + repr(e), flush=True)
            continue
        # 驱动几帧
        for _ in range(6):
            try:
                pet.update_movement()
            except Exception:
                break
        st = pet.__dict__.get('_scene_state')
        cam = pet.__dict__.get('_scene_camera')
        print('  scene_id  = ' + repr(getattr(st, 'scene_id', None)), flush=True)
        print('  scene obj = ' + repr(type(st).__name__ if st else None),
              flush=True)
        if st is not None:
            for k in ('bg', 'bg_name', 'room_id', 'chapter_id', 'w', 'h',
                      'width', 'height', 'objects'):
                if hasattr(st, k):
                    v = getattr(st, k)
                    if k == 'objects':
                        print('  st.%s n=%d' % (k, len(v or [])), flush=True)
                    else:
                        print('  st.%s = %r' % (k, v), flush=True)
        print('  cam.rect = ' + repr(None if cam is None else cam.rect),
              flush=True)
        try:
            plan = pet.scene.plan_frame() or []
        except Exception as e:
            print('  plan EXC ' + repr(e), flush=True)
            plan = []
        for i, it in enumerate(plan):
            if not isinstance(it, dict):
                continue
            print('    [%d] kind=%s name=%r rect=%r reason=%r'
                  % (i, it.get('kind'), it.get('name'), it.get('rect'),
                     it.get('reason')), flush=True)
        # 直接看缓存能不能取到 bg
        try:
            cv = pet.__dict__.get('scene_canvas')
            cache = getattr(cv, 'assets', None) if cv is not None else None
            print('  canvas=%r cache=%r' % (
                None if cv is None else (cv.isVisible(), cv.width(),
                                         cv.height(),
                                         getattr(cv, '_view_size', None)),
                type(cache).__name__ if cache else None), flush=True)
            if cache is not None and st is not None:
                for nm in (getattr(st, 'bg', None),
                           getattr(st, 'bg_name', None)):
                    if nm:
                        pm = None
                        try:
                            pm = cache.get(nm)
                        except Exception as e:
                            print('    cache.get(%r) EXC %r' % (nm, e),
                                  flush=True)
                            continue
                        print('    cache.get(%r) -> %r' % (
                            nm, None if pm is None else
                            (pm.width(), pm.height())), flush=True)
            miss = getattr(cache, 'missing', None) if cache else None
            fail = getattr(cache, '_failed', None) if cache else None
            print('    cache.missing=%r _failed=%r' % (
                list(miss)[:8] if miss else miss, fail), flush=True)
        except Exception as e:
            print('  canvas EXC ' + repr(e), flush=True)
    print('\n[DONE]', flush=True)
    app.quit()


QTimer.singleShot(3000, go)
app.exec_()
