# -*- coding: utf-8 -*-
"""第162轮 · 落点与任务栏（真窗口，沙箱副本）。

要回答一件事：**宠物静止时，脚到底站在任务栏上沿，还是被任务栏压住？**
产品里有两个"地面"：
  · `_desktop_floor_y()`  = 整屏底边（含任务栏那条）  ← 坠落/弹跳用
  · `_taskbar_top_y()`    = 工作区底边（扣掉任务栏）  ← 待机"窝着"用
两者不一致时，用户看到的就是"人沉到快捷栏底下去了"。

本支输出：屏几何 / 工作区 / 任务栏上沿 / 宠物逐秒位置 / 精灵矩形 / 两者差值。
"""
import os
import sys
import time
import traceback

SANDBOX = r"D:\_tmp\pet162"
os.environ['RALSEI_DATA_DIR'] = r"D:\_tmp\pet162_data"
os.environ.pop('QT_QPA_PLATFORM', None)

sys.path.insert(0, os.path.join(SANDBOX, 'modules'))
sys.path.insert(0, os.path.join(SANDBOX, 'src'))
try:
    import memory_store as _ms
    _ms.find_device_dir = lambda create=True: None
except Exception:
    pass
try:
    import data_store as _ds
    _ds.vault_root = lambda create=True: None
except Exception:
    pass

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)
from main import RalseiPet

w = RalseiPet()
w.show()


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def snap(tag):
    g = w.frameGeometry()
    sl = w.sprite_label.geometry()
    print('[SNAP] %-10s pos=(%d,%d) size=%dx%d bottom=%d sprite=%dx%d@(%d,%d) anim=%s drag=%s'
          % (tag, g.x(), g.y(), g.width(), g.height(), g.y() + g.height(),
             sl.width(), sl.height(), sl.x(), sl.y(),
             getattr(w, 'current_animation', '?'),
             getattr(w, '_is_being_dragged', None)), flush=True)


try:
    scr = app.primaryScreen()
    print('[SCR] geometry   = %s' % (scr.geometry().getRect(),), flush=True)
    print('[SCR] available  = %s' % (scr.availableGeometry().getRect(),), flush=True)
    print('[SCR] virtual    = %s' % (w._virtual_screen_rect().getRect(),), flush=True)
    print('[SCR] work_area  = %s' % (w._work_area_rect().getRect(),), flush=True)
    print('[SCR] floor_y(screen) = %d' % w._desktop_floor_y(), flush=True)
    print('[SCR] taskbar_top_y   = %d' % w._taskbar_top_y(), flush=True)
    print('[SCR] 差 = %d px' % (w._desktop_floor_y() - w._taskbar_top_y()), flush=True)

    for i in range(4):
        pump(1000)
        snap('t=%ds' % (i + 1))

    # 强制一次"从高处掉下来"，看它落在哪条底边
    print('[ACT] 抬到 (x, 100) 后 start_fall', flush=True)
    w.move(w.x(), 100)
    pump(100)
    try:
        w.start_fall(reason='probe162')
    except Exception:
        print('[ERR] start_fall: %s' % traceback.format_exc(), flush=True)
    for i in range(6):
        pump(500)
        snap('fall+%.1fs' % (i * 0.5 + 0.5))

    # 待机窝点：产品认为应该站哪儿
    print('[ACT] _lounge_perch_point() = %s' % (getattr(w, '_lounge_perch_point', lambda: None)(),), flush=True)

    # 点击热区：窗口内、精灵外的那块到底算不算命中
    sl = w.sprite_label.geometry()
    print('[HIT] 窗口 %dx%d / 精灵 %dx%d ⇒ 空白 %d px' % (
        w.width(), w.height(), sl.width(), sl.height(),
        w.width() * w.height() - sl.width() * sl.height()), flush=True)
finally:
    try:
        w.cleanup_on_exit()
    except Exception:
        pass
    app.quit()
print('[DONE]', flush=True)
