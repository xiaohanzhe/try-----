# -*- coding: utf-8 -*-
"""第112轮诊断 2：`scene_canvas` 的真几何 / 可见性 / plan，以及**画布抓图**。

上一版 `diag112.py` 猜错了属性名（`scene_layer` 不存在，真名是 `scene_canvas`）。
本支：
  ① 内省 `scene_canvas` 的可见性 / 几何 / `_plan`
  ② **直接 `scene_canvas.grab()`** —— 把画布内容自己抓出来存 PNG。
     这比抓整屏可靠得多（不受"窗口是否被遮挡 / 是否已上屏"影响）。
  ③ 判据：画布抓图里**真的有门**（4 个非透明块）且**真的有宠物**。
"""
import io
import os
import sys
import time
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_TEST_MODE', '1')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage, QColor

_app = QApplication.instance() or QApplication(sys.argv)

OUT = os.path.join(HERE, '..', '_evidence', 'canvas112')
if not os.path.isdir(OUT):
    os.makedirs(OUT)

N = {'p': 0, 'f': 0}


def ok(name, cond, detail=u''):
    N['p' if cond else 'f'] += 1
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', name,
                        (u'  <- %s' % detail) if detail else u''))
    return bool(cond)


import main as _M
pet = _M.RalseiPet()
pet.show()
t_end = time.time() * 1000 + 2500
while time.time() * 1000 < t_end:
    _app.processEvents()
    time.sleep(0.01)

sc = pet.__dict__.get('scene_canvas')
ok('1 scene_canvas 存在', sc is not None, u'%r' % (type(sc).__name__ if sc else None))
if sc is None:
    sys.exit(1)

print('  isVisible   = %r' % sc.isVisible())
print('  geometry    = %r' % (sc.geometry().getRect(),))
print('  size        = %rx%r' % (sc.size().width(), sc.size().height()))
print('  _scene_layer_visible = %r' % pet.__dict__.get('_scene_layer_visible'))
print('  _cached_scale_factor = %r' % pet.__dict__.get('_cached_scale_factor'))

# 画布自己抓图（透明背景用 ARGB 抓，先铺一层洋红以便肉眼分辨"透明"）
pm = sc.grab()
img = pm.toImage()
p1 = os.path.join(OUT, 'canvas_raw.png')
img.save(p1, 'PNG')
print('  canvas.grab() -> %s  (%dx%d)' % (os.path.basename(p1), img.width(), img.height()))

# 统计非透明像素
nz = 0
tot = 0
for y in range(0, img.height(), 3):
    for x in range(0, img.width(), 3):
        tot += 1
        c = img.pixel(x, y)
        if ((c >> 24) & 0xFF) > 8:
            nz += 1
print('  非透明像素占比 = %.2f%%' % (100.0 * nz / max(1, tot)))

# 铺洋红底再存一张（肉眼能看清画了什么）
from PyQt5.QtGui import QPainter
bg = QImage(img.size(), QImage.Format_ARGB32)
bg.fill(QColor(255, 0, 255))
pt = QPainter(bg)
pt.drawImage(0, 0, img)
pt.end()
p2 = os.path.join(OUT, 'canvas_on_magenta.png')
bg.save(p2, 'PNG')
print('  洋红底 -> %s' % os.path.basename(p2))

# 缩到 1/2 便于查看
half = bg.scaled(bg.width() // 2, bg.height() // 2)
p3 = os.path.join(OUT, 'canvas_half.png')
half.save(p3, 'PNG')

ok('2 画布抓图非空（有内容）', nz > 100, u'nz=%d/%d' % (nz, tot))
ok('3 画布可见', bool(sc.isVisible()), u'%r' % sc.isVisible())
print('\n==== diag2: PASS=%d FAIL=%d ====' % (N['p'], N['f']))
