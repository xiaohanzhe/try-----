# -*- coding: utf-8 -*-
"""第51轮观测器：宠物**动画**是否在播（像素差分）+ 窗口是否在动。

用法：python anim_probe51.py --pid 10756 --frames 10 --interval 0.15 --out <dir>
输出：每帧与首帧的差异像素数；以及帧间差异。≥1 说明画面在变（动画在播）。
"""
import argparse
import os
import sys
import time

from PyQt5.QtGui import QGuiApplication
from PyQt5.QtCore import QRect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shot51 import win_rects_for_pid            # noqa: E402


def grab(scr, x, y, w, h):
    pm = scr.grabWindow(0, x, y, w, h)
    img = pm.toImage()
    px = []
    for j in range(img.height()):
        row = []
        for i in range(img.width()):
            c = img.pixel(i, j)
            row.append((c >> 16 & 255, c >> 8 & 255, c & 255))
        px.append(row)
    return px


def diff(a, b):
    n = 0
    total = 0
    for j in range(min(len(a), len(b))):
        ra, rb = a[j], b[j]
        for i in range(min(len(ra), len(rb))):
            pa, pb = ra[i], rb[i]
            d = abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2])
            if d > 24:
                n += 1
            total += 1
    return n, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--frames', type=int, default=10)
    ap.add_argument('--interval', type=float, default=0.15)
    ap.add_argument('--out', default='')
    a = ap.parse_args()

    app = QGuiApplication(sys.argv)          # noqa: F841
    scr = QGuiApplication.primaryScreen()
    ws = win_rects_for_pid(a.pid)
    if not ws:
        print('没有可见窗口'); return 1
    ws = sorted(ws, key=lambda r: r[3] * r[4])
    hwnd, x, y, w, h = ws[0]
    print('宠物窗口 hwnd=%s rect=(%d,%d,%d,%d)' % (hwnd, x, y, w, h))
    pad = 6
    X, Y, W, H = x - pad, y - pad, w + pad * 2, h + pad * 2
    if a.out:
        os.makedirs(a.out, exist_ok=True)

    frames = []
    rects = []
    for k in range(a.frames):
        r = win_rects_for_pid(a.pid)
        r = sorted(r, key=lambda q: q[3] * q[4])[0]
        rects.append((r[1], r[2]))
        px = grab(scr, X, Y, W, H)
        frames.append(px)
        if a.out:
            scr.grabWindow(0, X, Y, W, H).save(
                os.path.join(a.out, 'anim_%02d.png' % k), 'PNG')
        time.sleep(a.interval)

    print('帧间差异（像素数 >24 灰度差）：')
    for k in range(1, len(frames)):
        n, total = diff(frames[k - 1], frames[k])
        print('  frame %2d -> %2d : %5d / %5d 像素变化 (%.1f%%)  窗口@%r'
              % (k - 1, k, n, total, 100.0 * n / max(1, total), rects[k]))
    n0, total0 = diff(frames[0], frames[-1])
    print('  首帧 vs 末帧 : %5d / %5d (%.1f%%)' % (n0, total0,
                                                   100.0 * n0 / max(1, total0)))
    uniq = len(set(rects))
    print('  窗口位置去重数 = %d / %d （1 = 完全没动）' % (uniq, len(rects)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
