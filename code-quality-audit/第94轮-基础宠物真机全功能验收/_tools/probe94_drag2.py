# -*- coding: utf-8 -*-
"""第94轮 · S5 定点探针：拖拽过程中"窗口中心 vs 角色中心"逐步对账。

要回答的问题：S5.2 报的"窗口中心单步偏差 11px"到底是
  (a) **角色在屏幕上真的跳了 11px**，还是
  (b) **只有窗口矩形在跳**（动画切换时容器尺寸变化 + 按中心重排窗口），角色没动？

判定办法：逐步记录 (dx, dy, w, h, anim, 窗口中心)，并额外记录
`_anim_anchor_offset(anim)`（该动画里"角色 alpha 包围盒中心"相对帧原点的偏移），
用它反推**角色中心在屏幕上的绝对位置**：
    角色中心x ≈ 窗口x + (w - 帧宽*scale)/2 + (off_x*scale) + 帧宽*scale/2
              = 窗口x + w/2 - off局... 太绕，改为**直接量**：
    劫持 `p.sprite_label.pixmap()` 拿不到 ⇒ 换做法：直接看"角色中心 = 窗口中心"这条
    是否成立 —— 成立则窗口中心连续 ⇒ 角色连续。
本探针只报告数据，不下结论。
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
OUT = os.path.join(EVID, 'probe94_drag2.txt')
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


from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QPointF, Qt, QEvent
from PyQt5.QtGui import QMouseEvent

app = QApplication.instance() or QApplication(sys.argv)
import main as main_mod

p = main_mod.RalseiPet()
app.processEvents()
if not p.isVisible():
    p.show()
app.processEvents()
w('=== 第94轮 S5 定点探针（拖拽逐步对账）===')
w('时间 = %s' % time.strftime('%Y-%m-%d %H:%M:%S'))

g = app.primaryScreen().availableGeometry()
p.move(g.center().x() - p.width() // 2, g.center().y() - p.height() // 2)
for _ in range(20):
    app.processEvents()
    time.sleep(0.02)
sxp, syp = p.x(), p.y()
w0, h0 = p.width(), p.height()
w('起点 = (%d,%d) size=%dx%d anim=%r' % (sxp, syp, w0, h0, p.current_animation))

local = QPointF(20.0, 20.0)
p.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, local,
                              QPointF(float(sxp + 20), float(syp + 20)),
                              Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
app.processEvents()
w('press: anim=%r size=%dx%d' % (p.current_animation, p.width(), p.height()))
w()
w('  i | 期望(dx,dy) | 实际(dx,dy) | size    | 容器/2  | 窗口中心相对起点      | anim')
rows = []
for i in range(1, 21):
    gx = QPointF(float(sxp + 20 + i * 8), float(syp + 20 + i * 4))
    p.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, local, gx,
                                 Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    app.processEvents()
    time.sleep(0.03)
    ww, hh = p.width(), p.height()
    dx, dy = p.x() - sxp, p.y() - syp
    cx = p.x() + ww // 2 - sxp
    cy = p.y() + hh // 2 - syp
    rows.append((i, dx, dy, ww, hh, cx, cy, p.current_animation))
    w('  %2d |   (%3d,%3d)   |   (%3d,%3d)   | %3dx%-3d | %3d,%-3d | (%5d,%5d) | %s'
      % (i, i * 8, i * 4, dx, dy, ww, hh, ww // 2, hh // 2, cx, cy, p.current_animation))

w()
w('--- 逐步差分（相对上一步）---')
# ★ 基线必须是**按下前**的真实中心（相对起点 = (w0//2, h0//2)），
#   不能拿 (0,0) 起算 —— 否则第 1 步会被算成"偏差 69/47"，那是探针的基线 bug。
prev = (0, 0, w0, h0, w0 // 2, h0 // 2)
for (i, dx, dy, ww, hh, cx, cy, anim) in rows:
    dcx, dcy = cx - prev[4], cy - prev[5]
    w('  i=%2d  Δ中心=(%3d,%3d)  期望=(%2d,%2d)  偏差=(%3d,%3d)  Δ尺寸=(%4d,%4d)  anim=%s'
      % (i, dcx, dcy, 8, 4, dcx - 8, dcy - 4, ww - prev[2], hh - prev[3], anim))
    prev = (dx, dy, ww, hh, cx, cy)

w()
w('--- 终点（最后一步）左上角是否精确跟随 ---')
w('  末步 实际(dx,dy)=(%d,%d)  期望=(160,80)' % (rows[-1][1], rows[-1][2]))

# 释放（慢放，不触发甩飞）
p.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, local,
                                QPointF(float(sxp + 20 + 160), float(syp + 20 + 80)),
                                Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
for _ in range(15):
    app.processEvents()
    time.sleep(0.02)
w('  松手后 0.3s: pos=(%d,%d) size=%dx%d anim=%r  中心相对起点=(%d,%d)'
  % (p.x() - sxp, p.y() - syp, p.width(), p.height(), p.current_animation,
     p.x() + p.width() // 2 - sxp, p.y() + p.height() // 2 - syp))
try:
    p.close()
except Exception:
    pass
os._exit(0)
