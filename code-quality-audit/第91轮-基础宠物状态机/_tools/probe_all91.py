# -*- coding: utf-8 -*-
"""第91轮：全局探测 —— 所有 python 进程 + 所有标题/类名含 ralsei 的顶层窗口。

用来回答两件事：
  1. 起宠的 pid 到底是不是承载 Qt 窗口的那个 pid？
  2. 现在还有没有 ralsei 窗口（有没有复现「宠物消失」）。
"""
import ctypes
from ctypes import wintypes

import psutil

u = ctypes.WinDLL('user32')
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.IsWindowVisible.argtypes = [wintypes.HWND]

print('===== 所有 python 进程 =====')
for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
    try:
        if p.info['name'] and 'python' in p.info['name'].lower():
            cl = ' '.join(p.info['cmdline'] or [])
            if 'main.py' in cl or 'monitor' in cl or 'ralsei' in cl.lower():
                print('  pid=%-7d %s' % (p.info['pid'], cl[:110]))
    except Exception:
        pass

print('\n===== 所有标题或类名含 ralsei / Qt 的顶层窗口 =====')
rows = []


def cb(h, l):
    n = u.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 2)
    u.GetWindowTextW(h, b, n + 2)
    c = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, c, 256)
    ti, cl = b.value, c.value
    if 'ralsei' in ti.lower() or 'ralsei' in cl.lower() or 'Qt5' in cl:
        d = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(d))
        r = wintypes.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        rows.append((int(h), d.value, r.left, r.top, r.right - r.left, r.bottom - r.top,
                     bool(u.IsWindowVisible(h)), ti, cl))
    return True


u.EnumWindows(CB(cb), 0)
print('命中 %d 个：' % len(rows))
print('%-10s %-8s %-6s %-6s %-6s %-6s %-6s %-8s %s' % ('hwnd', 'pid', 'left', 'top', 'w', 'h', 'area', 'visible', 'title|class'))
for r in sorted(rows, key=lambda x: abs(x[4] * x[5])):
    print('%-10d %-8d %-6d %-6d %-6d %-6d %-6d %-8s %s | %s'
          % (r[0], r[1], r[2], r[3], r[4], r[5], r[4] * r[5], r[6], r[7], r[8]))
