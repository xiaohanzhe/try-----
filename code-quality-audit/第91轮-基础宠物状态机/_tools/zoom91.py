# -*- coding: utf-8 -*-
"""第91轮：把宠物每个可见窗口的屏幕区域**裁剪+放大 4 倍**，用于人眼判读精灵外观。

为什么不能用 PrintWindow：桌宠是透明分层窗口，PrintWindow 拿到 ~1% 像素。
必须走"整屏 GDI 抓屏 → 按窗口矩形裁剪"，那才是人眼看到的画面。
"""
import ctypes
import os
import sys
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import monitor91 as M  # noqa: E402
import cv2  # noqa: E402

u = M.user32
PID = int(sys.argv[1]) if len(sys.argv) > 1 else 4712
OUTD = r'C:\Users\23002\Downloads\_tmp'
os.makedirs(OUTD, exist_ok=True)

CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]

wins = []


def cb(h, l):
    d = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(d))
    if d.value == PID and u.IsWindowVisible(h):
        r = wintypes.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        w, hh = r.right - r.left, r.bottom - r.top
        if w > 0 and hh > 0:
            wins.append((int(h), r.left, r.top, w, hh, w * hh))
    return True


u.EnumWindows(CB(cb), 0)
wins.sort(key=lambda x: x[5])
print('pid=%d 可见窗口 %d 个' % (PID, len(wins)))

VW, VH = 2560, 1600
for i, (h, l, t, w, hh, area) in enumerate(wins):
    m = 40
    x, y = max(0, l - m), max(0, t - m)
    cw, ch = min(VW, l + w + m) - x, min(VH, t + hh + m) - y
    if cw <= 2 or ch <= 2:
        continue
    img = M.grab(x, y, cw, ch)
    big = cv2.resize(img, (cw * 4, ch * 4), interpolation=cv2.INTER_NEAREST)
    p = os.path.join(OUTD, 'zoom%d_%dx%d_at%d_%d.png' % (i, w, hh, l, t))
    cv2.imencode('.png', big)[1].tofile(p)
    print('  #%d hwnd=%d rect=(%d,%d,%dx%d) area=%d -> %s'
          % (i, h, l, t, w, hh, area, os.path.basename(p)))
