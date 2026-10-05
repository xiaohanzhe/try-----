# -*- coding: utf-8 -*-
u"""第89轮诊断 C：真机路径下，为什么 `plan_frame` 出 placeholder 而不是 bg。

`real_switch89b` 实测：
    desktop  → plan n=8 kinds={'obj': 8}          （无 placeholder）
    ch1.castle_town → plan n=4 kinds={'bg':1,'obj':2,'room_border':1}  ← 有 bg！
    uty.rooms.rm_intro → plan n=1 kinds={'placeholder': 1}
    oneshot.barrens.Blue → plan n=2 kinds={'placeholder':1,'room_border':1}

⇒ 关键发现：**ch1 其实是好的（出了 bg 指令）**，但抓出来 15255 bytes 灰图。
  而 uty / oneshot 出的是 `placeholder`。

本脚本查两件事：
  1. `plan_frame` 里 placeholder 的**产生条件**（scene/objects 里的 bg 名取不到？
     还是 scene 的 bg 字段本身就是空）。
  2. ch1 的 bg 指令 rect 是 (-640,-1840,1280,2320) —— **负坐标**，落笔时是否被
     裁到画布内；以及 `set_plan` 之后 `SceneCanvas` 的 `_view_size` 是多大。

在真机进程里跑（因为素材缓存行为可能依赖平台插件）。
"""
import os
import subprocess
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SH = os.path.join(HERE, '..', '_evidence', 'shots')

DRV = u'''# -*- coding: utf-8 -*-
import os, sys
PKG = __PKG__
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
        print('\\n===== ' + t + ' =====', flush=True)
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
    print('\\n[DONE]', flush=True)
    app.quit()


QTimer.singleShot(3000, go)
app.exec_()
'''


def main():
    src = DRV.replace('__PKG__', repr(PKG))
    drv = os.path.join(HERE, '_drv89c.py')
    with open(drv, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(src)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env.pop('QT_QPA_PLATFORM', None)
    env['RALSEI_MEMORY_DIR'] = os.path.join(
        os.environ.get('TEMP', '.'), 'ralsei_real89c')
    logp = os.path.join(SH, 'diag_c.log')
    with open(logp, 'w', encoding='utf-8', newline='\n') as log:
        p = subprocess.Popen([sys.executable, drv], cwd=PKG, env=env,
                             stdout=log, stderr=subprocess.STDOUT)
        for _ in range(60):
            if p.poll() is not None:
                break
            time.sleep(1)
        if p.poll() is None:
            p.terminate()
            time.sleep(1)
            if p.poll() is None:
                p.kill()
    with open(logp, encoding='utf-8', errors='replace') as fh:
        print(fh.read())
    return 0


if __name__ == '__main__':
    sys.exit(main())
