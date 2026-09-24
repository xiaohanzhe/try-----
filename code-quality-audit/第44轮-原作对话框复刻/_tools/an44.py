# -*- coding: utf-8 -*-
"""第44轮 · 对已落盘 UI 截图做像素体检：非透明包围盒 + 逐行扫描。"""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.dirname(os.path.abspath(__file__))
EVID = os.path.abspath(os.path.join(HERE, '..', '_evidence'))

from PyQt5.QtGui import QImage            # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402


def analyze(path):
    img = QImage(path)
    if img.isNull():
        print('[ERR] 打不开 %s' % path)
        return
    W, H = img.width(), img.height()
    print('=== %s  %dx%d ===' % (os.path.basename(path), W, H))
    # 非透明包围盒
    minx, miny, maxx, maxy = W, H, -1, -1
    for y in range(H):
        for x in range(W):
            if img.pixelColor(x, y).alpha() != 0:
                if x < minx:
                    minx = x
                if x > maxx:
                    maxx = x
                if y < miny:
                    miny = y
                if y > maxy:
                    maxy = y
    print('  非透明包围盒 = x[%d..%d] y[%d..%d]' % (minx, maxx, miny, maxy))
    # 中轴逐行
    cx = W // 2
    prev = None
    for y in range(H):
        c = img.pixelColor(cx, y)
        key = (c.red(), c.green(), c.blue(), c.alpha())
        if key != prev:
            print('    y=%-4d mid -> (r=%3d g=%3d b=%3d a=%3d)'
                  % (y, key[0], key[1], key[2], key[3]))
            prev = key


def main():
    _ = QApplication.instance() or QApplication(sys.argv)
    for n in ('ui44_full.png', 'ui44_corner.png'):
        analyze(os.path.join(EVID, n))
        print()


if __name__ == '__main__':
    main()
