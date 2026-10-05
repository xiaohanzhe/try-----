# -*- coding: utf-8 -*-
"""第91轮：把宠物主窗口临时提到 z 序顶部（不抢焦点），再抓它的屏幕区域。

为什么需要：桌宠是 `Qt.Tool` 且**不置顶**（用户裁定禁用 WindowStaysOnTopHint），
所以当前台全屏窗口（文件管理器）盖住时，整屏截图里看到的**不是宠物**。
`SetWindowPos(HWND_TOP, SWP_NOACTIVATE)` 只改 z 序、不改位置大小、不抢焦点，
取证完用户点一下别处就恢复 —— 属最小侵入且完全可逆。
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import monitor91 as M  # noqa: E402
import cv2  # noqa: E402

u = M.user32
PID = int(sys.argv[1]) if len(sys.argv) > 1 else 4712
VW, VH = 2560, 1600
HWND_TOP = 0
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                           ctypes.c_int, ctypes.c_int, wintypes.UINT]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

wins = []


def cb(h, l):
    d = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(d))
    if d.value == PID and u.IsWindowVisible(h):
        r = wintypes.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        w, hh = r.right - r.left, r.bottom - r.top
        if 15 <= w <= 80 and 40 <= hh <= 110:      # 宠物本体尺寸窗口
            wins.append((int(h), r.left, r.top, w, hh))
    return True


u.EnumWindows(CB(cb), 0)
print('宠物本体候选窗口: %s' % wins)
for hwnd, l, t, w, hh in wins:
    u.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
time.sleep(0.5)

OUTD = r'C:\Users\23002\Downloads\_tmp'
for i, (hwnd, l, t, w, hh) in enumerate(wins):
    m = 30
    x, y = max(0, l - m), max(0, t - m)
    cw, ch = min(VW, l + w + m) - x, min(VH, t + hh + m) - y
    img = M.grab(x, y, cw, ch)
    big = cv2.resize(img, (cw * 4, ch * 4), interpolation=cv2.INTER_NEAREST)
    p = os.path.join(OUTD, 'pet91_%d_%dx%d_at%d_%d.png' % (i, w, hh, l, t))
    cv2.imencode('.png', big)[1].tofile(p)
    print('  #%d hwnd=%d (%d,%d %dx%d) -> %s' % (i, hwnd, l, t, w, hh, os.path.basename(p)))
print('done')
