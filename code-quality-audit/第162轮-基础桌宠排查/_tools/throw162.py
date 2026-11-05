# -*- coding: utf-8 -*-
"""第162轮 · 甩飞落点截图：摔下来以后，脚在任务栏上面还是下面。

走**真实鼠标路径**（press → 高速 move → release），不用 `start_fall` 直调
（第162轮实测：直调会卡在 splat/fall_back 不落地，那是我的调用姿势不对，
不是产品路径）。
"""
import os
import sys
import time
import traceback

SANDBOX = r"D:\_tmp\pet162"
os.environ['RALSEI_DATA_DIR'] = r'D:\_tmp\pet162_data'
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
from PyQt5.QtCore import Qt, QPoint, QEvent

app = QApplication(sys.argv)
from main import RalseiPet
from PyQt5.QtGui import QMouseEvent

w = RalseiPet()
w.show()


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


pump(2000)
wa = app.primaryScreen().availableGeometry()
work_bottom = wa.y() + wa.height()
print('[BASE] work_bottom=%d  pos=%s size=%dx%d' % (
    work_bottom, w.pos(), w.width(), w.height()), flush=True)


def ev(kind, gpt, buttons):
    local = w.mapFromGlobal(gpt)
    press = Qt.LeftButton if kind == QEvent.MouseButtonPress else Qt.NoButton
    e = QMouseEvent(kind, local, gpt, Qt.LeftButton, buttons, Qt.NoModifier)
    app.sendEvent(w, e)


g0 = w.mapToGlobal(w.rect().center())
ev(QEvent.MouseButtonPress, g0, Qt.LeftButton)
pump(30)
# 向斜上方猛拖，然后松手 —— 走产品自己的甩飞判定
for i in range(1, 7):
    gp = QPoint(g0.x() - 40 * i, g0.y() - 25 * i)
    ev(QEvent.MouseMove, gp, Qt.LeftButton)
    pump(20)
grel = QPoint(g0.x() - 240, g0.y() - 150)
ev(QEvent.MouseButtonRelease, grel, Qt.NoButton)
print('[THROW] 松手 _fall_reason=%r  pos=%s' % (getattr(w, '_fall_reason', None), w.pos()), flush=True)

for i in range(10):
    pump(500)
    g = w.frameGeometry()
    print('[TRACK] +%.1fs y=%d bottom=%d (工作区底 %d, 屏高 %d) anim=%s' % (
        (i + 1) * 0.5, g.y(), g.y() + g.height(), work_bottom,
        app.primaryScreen().geometry().height(),
        getattr(w, 'current_animation', '')), flush=True)

g = w.frameGeometry()
print('[FINAL] bottom=%d 越过工作区=%s' % (g.y() + g.height(), g.y() + g.height() > work_bottom), flush=True)

try:
    from PIL import ImageGrab
    pad = 30
    box = (max(0, g.x() - pad), max(0, g.y() - pad),
           g.x() + g.width() + pad, g.y() + g.height() + pad)
    ImageGrab.grab().crop(box).save(r'D:\_tmp\shot162_throw.png')
    print('[OK] 截图 D:\\_tmp\\shot162_throw.png', flush=True)
except Exception:
    print('[FAIL] 截图:\n%s' % traceback.format_exc(), flush=True)

try:
    w.cleanup_on_exit()
except Exception:
    pass
app.quit()
print('[DONE]', flush=True)
