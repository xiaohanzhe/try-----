# -*- coding: utf-8 -*-
u"""第89轮真机验证 B 版：**边切边自报病灶**。

与 `real_switch89.py` 的差别：驱动器在每次 `travel_to_scene` 之后，把
**本帧的真实摆位状态**打出来，逐项回答「到底是①计划为空 还是②有计划但没上屏」：

    cam.rect          —— 相机世界矩形（None = 相机没建）
    plan kinds        —— `plan_frame` 出的指令种类计数
    canvas.visible    —— 独立窗口是否 isVisible()
    canvas.rect       —— 窗口真几何（DPI 感知后的）
    canvas.size       —— 内容尺寸
    layer_visible     —— `_scene_layer_visible` 旗标
    bg name/rect      —— bg 指令（若计划为空则为 None）

父进程负责抓图；两边一起看就能分清「没画」和「画了但在屏外」。
"""
import ctypes
import os
import subprocess
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SH = os.path.join(HERE, '..', '_evidence', 'shots')

DRIVER_HEAD = u'''# -*- coding: utf-8 -*-
import os, sys, time
PKG = __PKG__
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

TARGETS = __TARGETS__
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
    print('\\n'.join(out), flush=True)


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
'''


class RECT(ctypes.Structure):
    _fields_ = [('l', ctypes.c_long), ('t', ctypes.c_long),
                ('r', ctypes.c_long), ('b', ctypes.c_long)]


def main():
    targets = ['ch1.castle_town.castle_town', 'uty.rooms.rm_intro',
               'oneshot.barrens.Blue', 'desktop']
    os.makedirs(SH, exist_ok=True)

    src = (DRIVER_HEAD
           .replace('__PKG__', repr(PKG))
           .replace('__TARGETS__', repr(targets)))
    drv = os.path.join(HERE, '_drv89b.py')
    with open(drv, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(src)

    sys.path.insert(0, HERE)
    import grabwin89
    import winprobe89

    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env.pop('QT_QPA_PLATFORM', None)
    env['RALSEI_MEMORY_DIR'] = os.path.join(
        os.environ.get('TEMP', '.'), 'ralsei_real89b')

    logp = os.path.join(SH, 'real_switch_b.log')
    log = open(logp, 'w', encoding='utf-8', newline='\n')
    p = subprocess.Popen([sys.executable, drv], cwd=PKG, env=env,
                         stdout=log, stderr=subprocess.STDOUT)
    print('driver pid', p.pid)

    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    time.sleep(8)
    tags = ['00_start'] + ['%02d_%s' % (i + 1, t.replace('.', '_')[:22])
                           for i, t in enumerate(targets)]

    for tag in tags:
        time.sleep(9)
        print('--- 抓 %s ---' % tag)

        def cb(h, _l, _pid=p.pid, _tag=tag):
            if winprobe89.pid_of(h) != _pid:
                return True
            c = winprobe89.cls(h)
            if c == 'IME':
                return True
            rr = RECT()
            ctypes.windll.user32.GetWindowRect(h, ctypes.byref(rr))
            w, hh = rr.r - rr.l, rr.b - rr.t
            kind = None
            if (w, hh) == (640, 480):
                kind = 'canvas'
            elif 560 < w < 700 and 180 < hh < 320:
                kind = 'dialog'
            if kind is None:
                return True
            img, _w, _h = grabwin89.grab(h)
            if img is not None and not img.isNull():
                fp = os.path.join(SH, 'rb_%s_%s.png' % (_tag, kind))
                img.save(fp, 'PNG')
                sz = os.path.getsize(fp)
                print('  %-7s rect=%s -> %s (%d bytes)'
                      % (kind, (rr.l, rr.t, w, hh),
                         os.path.basename(fp), sz))
            return True

        winprobe89.EnumWindows(winprobe89.P(cb), 0)

    try:
        p.terminate()
        time.sleep(1.5)
        if p.poll() is None:
            p.kill()
    except Exception:
        pass
    log.close()

    print('\n--- driver 自报状态（[STATE]/[DRV] 行）---')
    with open(logp, encoding='utf-8', errors='replace') as fh:
        for ln in fh:
            if '[STATE]' in ln or '[DRV]' in ln or 'cam=' in ln or 'plan ' in ln:
                print('  ' + ln.rstrip()[:200])
    return 0


if __name__ == '__main__':
    sys.exit(main())
