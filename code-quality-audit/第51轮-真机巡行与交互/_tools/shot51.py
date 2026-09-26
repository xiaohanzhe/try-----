# -*- coding: utf-8 -*-
"""第51轮观测器：真机抓屏（不依赖任何第三方屏幕自动化组件）。

用法：
    python shot51.py <输出png> [--full] [--pid <目标pid>] [--crop x,y,w,h]

  --full       抓整个虚拟桌面
  --pid        抓某个进程的可见窗口（枚举该 pid 的顶层窗口并取并集）
  默认         抓整个虚拟桌面

为什么自己写：
  ① 屏幕自动化小助手（ScreenAutomationHelper.exe）本机**未安装**，
     按 skill 安全边界不得擅自下载安装；
  ② 本脚本只用 Qt 自带的 `QScreen.grabWindow(0)` + Win32 窗口枚举，
     零新增依赖，且能同时给出"宠物窗口矩形"这种结构化信息。
"""
import argparse
import ctypes
import os
import sys
from ctypes import wintypes

from PyQt5.QtGui import QGuiApplication


def win_rects_for_pid(pid):
    """枚举该 pid 的可见顶层窗口矩形（屏幕坐标）。"""
    user32 = ctypes.windll.user32
    out = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                                     wintypes.LPARAM)

    def cb(hwnd, _):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 0 or h <= 0:
            return True
        out.append((hwnd, r.left, r.top, w, h))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--pid', type=int, default=0)
    ap.add_argument('--crop', default='')
    a = ap.parse_args()

    app = QGuiApplication(sys.argv)          # noqa: F841  (抓屏前必须建 QGuiApplication)
    scr = QGuiApplication.primaryScreen()
    vs = QGuiApplication.primaryScreen().virtualGeometry()
    print('virtualGeometry = (%d, %d, %d, %d)'
          % (vs.x(), vs.y(), vs.width(), vs.height()))

    if a.pid:
        rects = win_rects_for_pid(a.pid)
        print('pid %d 的可见顶层窗口 %d 个:' % (a.pid, len(rects)))
        for r in rects:
            print('   hwnd=%s rect=(%d,%d,%d,%d)' % (r[0], r[1], r[2], r[3], r[4]))
        if rects:
            x0 = min(r[1] for r in rects)
            y0 = min(r[2] for r in rects)
            x1 = max(r[1] + r[3] for r in rects)
            y1 = max(r[2] + r[4] for r in rects)
            pad = 40
            x0, y0 = x0 - pad, y0 - pad
            w, h = (x1 - x0) + pad * 2, (y1 - y0) + pad * 2
            pm = scr.grabWindow(0, x0, y0, w, h)
        else:
            pm = scr.grabWindow(0)
    elif a.crop:
        x, y, w, h = [int(v) for v in a.crop.split(',')]
        pm = scr.grabWindow(0, x, y, w, h)
    else:
        pm = scr.grabWindow(0, vs.x(), vs.y(), vs.width(), vs.height())

    ok = pm.save(a.out, 'PNG')
    print('saved=%s size=%dx%d ok=%s' % (a.out, pm.width(), pm.height(), ok))
    return 0


if __name__ == '__main__':
    sys.exit(main())
