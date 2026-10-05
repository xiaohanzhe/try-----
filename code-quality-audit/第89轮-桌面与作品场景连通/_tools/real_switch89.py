# -*- coding: utf-8 -*-
u"""第89轮真机验证：**场景真能切换 + 屏幕上真能看到**（用户硬门槛）。

上一版探针的教训（必须记住）
--------------------------
`switch_probe89.py` 在 **offscreen** 下跑：`current_scene` 确实真切了、画布 plan
也确实重建了 —— **结论是对的**。但它 `canvas.grab()` 抓出来的图**每张都是 1292 字节的空白**
（offscreen 平台插件下独立窗口没有可见 surface）。
⇒ **"状态变了"不等于"屏幕上看得见"**。用户的门槛是后者。
这正是记忆里那句「**产物侧看不见 ≠ 调用侧没发生**」的镜像：
这次是「**调用侧发生了 ≠ 产物侧看得见**」，两个方向都要单独验。

本脚本的解法：**真机起 + 进程内切 + 进程外抓**
--------------------------------------------
  1. 用真窗口平台（不设 QT_QPA_PLATFORM）起一个子进程，它跑一段**驱动器脚本**：
     起 RalseiPet → 等 4s → `travel_to_scene(目标)` → 进入事件循环并停在那里。
     ★ 驱动脚本用 **字符串拼接** 写目标列表（不用 `%r` 模板替换 —— 会被一并 replace 掉）。
  2. 父进程用 `PrintWindow`（PW_RENDERFULLCONTENT=2）**逐窗口抓图** ——
     这是唯一能抓到 `WA_TranslucentBackground` 分层窗口内容的方式。
  3. 每个目标场景抓一套画布 + 对话框，落 `_evidence/shots/real_*`。
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

DRIVER_HEAD = '''# -*- coding: utf-8 -*-
import os, sys, time
PKG = __PKG__
for _p in (os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    sys.path.append(_p)
os.environ.pop('QT_QPA_PLATFORM', None)
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
app = QApplication.instance() or QApplication([])
from main import RalseiPet
pet = RalseiPet()
pet.BEDTIME_ENABLED = False
pet._npc_roam_last_tick = float('inf')

TARGETS = __TARGETS__
STEP_MS = 9000
_idx = [0]


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
    drv = os.path.join(HERE, '_drv89.py')
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
        os.environ.get('TEMP', '.'), 'ralsei_real89')

    logp = os.path.join(SH, 'real_switch.log')
    log = open(logp, 'w', encoding='utf-8', newline='\n')
    p = subprocess.Popen([sys.executable, drv], cwd=PKG, env=env,
                         stdout=log, stderr=subprocess.STDOUT)
    print('driver pid', p.pid)

    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    time.sleep(8)
    tags = ['00_start'] + ['%02d_%s' % (i + 1, t.replace('.', '_')[:22])
                           for i, t in enumerate(targets)]

    class _Ctx:
        pass

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
                fp = os.path.join(SH, 'real_%s_%s.png' % (_tag, kind))
                img.save(fp, 'PNG')
                sz = os.path.getsize(fp)
                print('  %-7s -> %s (%d bytes)' % (kind, os.path.basename(fp), sz))
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

    print('\n--- driver 日志（[DRV] 行）---')
    with open(logp, encoding='utf-8', errors='replace') as fh:
        for ln in fh:
            if '[DRV]' in ln:
                print('  ' + ln.rstrip()[:160])
    return 0


if __name__ == '__main__':
    sys.exit(main())
