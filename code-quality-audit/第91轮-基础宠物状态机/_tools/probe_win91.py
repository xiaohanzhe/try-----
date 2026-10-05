# -*- coding: utf-8 -*-
"""第91轮：枚举某 pid 的**全部**顶层窗口（尺寸/可见性/标题/类名），用于锁定「宠物本体」。

背景：一个桌宠实例其实有**多个**顶层窗口（对话框 620x255 / 宠物头 40x40 /
宠物身 44x58 / 灵魂 48x48 …）。之前 monitor91.py 取"面积最大的匹配窗口"⇒
抓到的是**对话框**（不动），不是**会走动的宠物本体**。
本脚本先把窗口集合打出来，再据此定筛选规则。
"""
import ctypes
import sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 25616

u = ctypes.WinDLL('user32')
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.IsWindowVisible.argtypes = [wintypes.HWND]

out = []


def cb(h, l):
    d = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(d))
    if d.value == PID:
        r = wintypes.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        n = u.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(n + 2)
        u.GetWindowTextW(h, b, n + 2)
        c = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(h, c, 256)
        out.append((int(h), r.left, r.top, r.right - r.left, r.bottom - r.top,
                    bool(u.IsWindowVisible(h)), b.value, c.value))
    return True


u.EnumWindows(CB(cb), 0)
print('pid=%d 的顶层窗口 %d 个（按面积升序）：' % (PID, len(out)))
print('%-10s %-6s %-6s %-6s %-6s %-6s %-8s %s' % ('hwnd', 'left', 'top', 'w', 'h', 'area', 'visible', 'title/class'))
for o in sorted(out, key=lambda x: abs(x[3] * x[4])):
    hh, lf, tp, w, h_, vis, ti, cl = o
    print('%-10d %-6d %-6d %-6d %-6d %-6d %-8s %s | %s' % (hh, lf, tp, w, h_, w * h_, vis, ti, cl))
