# -*- coding: utf-8 -*-
"""第51轮：点一个坐标 → 立刻抓屏（同一个进程内，避免"抓的时候弹窗已经关了"）。

用法：python click_shot51.py <x> <y> <out.png> [--delay 0.8] [--restore x,y] [--right]
"""
import argparse
import ctypes
import os
import sys
import time

from PyQt5.QtGui import QGuiApplication

u32 = ctypes.windll.user32


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('x', type=int)
    ap.add_argument('y', type=int)
    ap.add_argument('out')
    ap.add_argument('--delay', type=float, default=0.8)
    ap.add_argument('--restore', default='')
    ap.add_argument('--right', action='store_true')
    a = ap.parse_args()

    app = QGuiApplication(sys.argv)          # noqa: F841
    scr = QGuiApplication.primaryScreen()

    class POINT(ctypes.Structure):
        _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]
    pt = POINT()
    u32.GetCursorPos(ctypes.byref(pt))
    before = (pt.x, pt.y)

    down, up = (0x0008, 0x0010) if a.right else (0x0002, 0x0004)
    u32.SetCursorPos(a.x, a.y)
    time.sleep(0.25)
    u32.mouse_event(down, 0, 0, 0, 0)
    time.sleep(0.08)
    u32.mouse_event(up, 0, 0, 0, 0)
    time.sleep(a.delay)

    pm = scr.grabWindow(0)
    ok = pm.save(a.out, 'PNG')
    print('点击 (%d,%d) 后 %.2fs 抓屏 → %s ok=%s size=%dx%d'
          % (a.x, a.y, a.delay, a.out, ok, pm.width(), pm.height()))

    rx, ry = ([int(v) for v in a.restore.split(',')] if a.restore else before)
    u32.SetCursorPos(rx, ry)
    print('鼠标已移回', (rx, ry))
    return 0


if __name__ == '__main__':
    sys.exit(main())
