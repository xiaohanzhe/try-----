# -*- coding: utf-8 -*-
"""第94轮 · 真机最小拖拽探针：逐步骤落盘，用来隔离 `probe94_full.py` 的 S5 硬死点。

每次写盘后 flush ⇒ 进程若在 C 层硬崩（无 traceback、finally 不执行），
也能从文件里看到**最后活到哪一步**。
"""
import ctypes
import io
import os
import sys
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'ralsei_pet')
for _p in (os.path.join(SRC, 'src'), SRC, os.path.join(SRC, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

EVID = os.path.join(ROOT, 'code-quality-audit', '第94轮-基础宠物真机全功能验收', '_evidence')
OUT = os.path.join(EVID, 'probe94_drag.txt')
_buf = []


def w(s=''):
    _buf.append(str(s))
    try:
        print(s, flush=True)
    except Exception:
        pass
    try:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(_buf))
    except Exception:
        pass


w('=== 第94轮 最小拖拽探针 ===')
w('时间 = %s' % time.strftime('%Y-%m-%d %H:%M:%S'))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QPointF, Qt, QEvent
from PyQt5.QtGui import QMouseEvent

app = QApplication.instance() or QApplication(sys.argv)
w('QApplication ok')

import main as main_mod
w('main.py = %s' % main_mod.__file__)

p = main_mod.RalseiPet()
app.processEvents()
w('RalseiPet ok  pos=(%d,%d) size=%dx%d' % (p.x(), p.y(), p.width(), p.height()))
w('  _is_being_dragged=%r  is_moving=%r' % (getattr(p, '_is_being_dragged', 'NA'),
                                            getattr(p, 'is_moving', 'NA')))

g = app.primaryScreen().availableGeometry()
p.move(g.center().x() - p.width() // 2, g.center().y() - p.height() // 2)
app.processEvents()
sx, sy = p.x(), p.y()
w('移到中央 -> (%d,%d)' % (sx, sy))

local = QPointF(20.0, 20.0)
w('--- 构造 press 事件 ---')
ev_press = QMouseEvent(QEvent.MouseButtonPress, local,
                       QPointF(float(sx + 20), float(sy + 20)),
                       Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
w('press 事件构造 ok  globalPos=%r  button=%r' % (ev_press.globalPos(), ev_press.button()))
w('--- 调 mousePressEvent ---')
p.mousePressEvent(ev_press)
app.processEvents()
w('mousePressEvent 返回 ok  drag_position=%r  _is_being_dragged=%r'
  % (getattr(p, 'drag_position', 'NA'), getattr(p, '_is_being_dragged', 'NA')))

for i in range(1, 6):
    gx = QPointF(float(sx + 20 + i * 10), float(sy + 20 + i * 5))
    ev_move = QMouseEvent(QEvent.MouseMove, local, gx,
                          Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    w('  move#%d 构造 ok globalPos=%r buttons=%r' % (i, ev_move.globalPos(), ev_move.buttons()))
    p.mouseMoveEvent(ev_move)
    app.processEvents()
    w('  move#%d 返回 ok  宠物=(%d,%d)  期望=(%d,%d)' % (i, p.x(), p.y(), sx + i * 10, sy + i * 5))

w('--- release ---')
ev_rel = QMouseEvent(QEvent.MouseButtonRelease, local,
                     QPointF(float(sx + 70), float(sy + 45)),
                     Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
p.mouseReleaseEvent(ev_rel)
app.processEvents()
w('mouseReleaseEvent 返回 ok  宠物=(%d,%d)' % (p.x(), p.y()))
w('=== 拖拽探针走完（未崩）===')
w('PASS 过：press/move×5/release 全部返回')

try:
    p.close()
except Exception:
    pass
os._exit(0)
