# -*- coding: utf-8 -*-
"""第112轮：从真机抓帧里裁出「门应该在的位置」+「Ralsei」，做成可复核的拼图。

为什么需要这一步：`grabWindow(0)` 抓的是**整屏**（2560×1600），直接看全图
根本看不清 44×99 的门。用户铁律「一定要看录像而不是只读后台输出」——
必须把**门/宠物所在的像素区域**放大出来给人看。

门位置（desktop.json，房间 320×240 → 屏幕 1066×800 @ scale 3.331，画面偏移 747,400）：
    A OneShot  (138,0)   44×56
    B Niko家   (138,184) 44×56
    C UT       (0,70)    44×99
    D 三角符文 (284,94)  36×52
⇒ 屏幕坐标 = 画面原点(747,400) + 房间坐标 × scale
"""
import io
import os
import sys

try:
    from PyQt5.QtGui import QImage, QPainter, QColor
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication
except Exception as e:
    print('PyQt5 不可用: %s' % e)
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
FR = os.path.join(HERE, '..', '_evidence', 'frames112')
OUT = os.path.join(HERE, '..', '_evidence', 'crops112')
if not os.path.isdir(OUT):
    os.makedirs(OUT)

_app = QApplication.instance() or QApplication(sys.argv)

SCALE = 3.33125
OX, OY = 747, 400          # 画面在屏幕里的偏移（取自真机日志）
SCREEN = (2560, 1600)

DOORS = [('A_oneshot', 138, 0, 44, 56),
         ('B_nikohome', 138, 184, 44, 56),
         ('C_ut', 0, 70, 44, 99),
         ('D_deltarune', 284, 94, 36, 52)]

src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(FR, 'k000_boot.png')
img = QImage(src)
print('src=%s  size=%dx%d' % (os.path.basename(src), img.width(), img.height()))
if img.isNull():
    print('读不到图')
    sys.exit(3)

sc = img.width() / float(SCREEN[0])
print('缩放比（相对 2560 设计）= %.4f' % sc)

# 门在屏幕上的矩形（含 8px 余量）
for name, rx, ry, rw, rh in DOORS:
    l = int((OX + rx * SCALE) * sc) - 8
    t = int((OY + ry * SCALE) * sc) - 8
    w = int(rw * SCALE * sc) + 16
    h = int(rh * SCALE * sc) + 16
    l = max(0, l)
    t = max(0, t)
    rect = img.copy(l, t, w, h)
    # 放大 4 倍便于肉眼看
    big = rect.scaled(rect.width() * 4, rect.height() * 4,
                      Qt.KeepAspectRatio, Qt.FastTransformation)
    p = os.path.join(OUT, 'door_%s.png' % name)
    big.save(p, 'PNG')
    print('  %-14s 屏幕(%d,%d %dx%d) -> %s' % (name, l, t, w, h, os.path.basename(p)))

# 拼一张总览：4 扇门横排
tiles = []
for name, _rx, _ry, _w, _h in DOORS:
    p = os.path.join(OUT, 'door_%s.png' % name)
    if os.path.isfile(p):
        tiles.append((name, QImage(p)))
if tiles:
    th = max(t[1].height() for t in tiles)
    tw = sum(t[1].width() for t in tiles) + 20 * (len(tiles) + 1)
    sheet = QImage(tw, th + 60, QImage.Format_ARGB32)
    sheet.fill(QColor(30, 30, 30))
    pt = QPainter(sheet)
    pt.setPen(QColor(255, 255, 255))
    x = 20
    for name, im in tiles:
        pt.drawImage(x, 40, im)
        pt.drawText(x, 28, name)
        x += im.width() + 20
    pt.end()
    sp = os.path.join(OUT, 'doors_sheet.png')
    sheet.save(sp, 'PNG')
    print('拼图 -> %s (%dx%d)' % (sp, sheet.width(), sheet.height()))
