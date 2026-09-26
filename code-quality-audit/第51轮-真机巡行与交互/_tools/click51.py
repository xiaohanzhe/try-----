# -*- coding: utf-8 -*-
"""第51轮：真机点一下某个屏幕坐标（用于打开任务栏托盘溢出区）。

用法：python click51.py <x> <y> [--restore x,y]
  · 用 Win32 SetCursorPos + mouse_event 做一次真实左键单击（不用第三方屏幕自动化组件）；
  · 默认点完把鼠标移回原处，避免打扰用户。
"""
import argparse
import ctypes
import sys
import time

u32 = ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def get_pos():
    class POINT(ctypes.Structure):
        _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]
    pt = POINT()
    u32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def click(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.15)
    u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('x', type=int)
    ap.add_argument('y', type=int)
    ap.add_argument('--restore', default='')
    ap.add_argument('--stay', action='store_true')
    ap.add_argument('--right', action='store_true')
    a = ap.parse_args()
    before = get_pos()
    print('原鼠标位置', before)
    global MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
    if a.right:
        MOUSEEVENTF_LEFTDOWN = 0x0008   # RIGHTDOWN
        MOUSEEVENTF_LEFTUP = 0x0010     # RIGHTUP
    u32.SetCursorPos(a.x, a.y)
    time.sleep(0.2)
    u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.06)
    u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.4)
    print('已单击 (%d, %d)' % (a.x, a.y))
    if a.stay:
        return 0
    if a.restore:
        rx, ry = [int(v) for v in a.restore.split(',')]
    else:
        rx, ry = before
    u32.SetCursorPos(rx, ry)
    print('鼠标已移回', (rx, ry))
    return 0


if __name__ == '__main__':
    sys.exit(main())
