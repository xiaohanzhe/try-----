# -*- coding: utf-8 -*-
"""第93轮 · 真机验收（2/2）：**首帧落点**的定钉版。

与 probe93_live.py 的区别：
  1/2 版按"形状判据"只盯宠物精灵窗（44x58），但 `init_ui` 里 `setGeometry(init_x, init_y, 100, 100)`
  作用在**主窗口**上（100x100 会被形状判据 18..90 直接滤掉），且它随后被缩成精灵尺寸并移动
  ⇒ 想抓到"落点那一瞬"，必须**高频轮询 + 记录每个 hwnd 的首次矩形**，不做任何尺寸过滤。

同时记录：类名/标题/可见性/是否置顶；并把 (2410,1378)/(2410,1450) 两个期望值直接对账。
"""
import ctypes
import sys
import time
from ctypes import wintypes

_u = ctypes.WinDLL("user32")
DPI = "n/a"
try:
    if _u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
        DPI = "PER_MONITOR_AWARE_V2"
except Exception:
    pass

PERIOD = float(sys.argv[1]) if len(sys.argv) > 1 else 0.025      # 秒
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0

CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
_u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]


def work_area():
    r = wintypes.RECT()
    _u.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
    return r.left, r.top, r.right, r.bottom


WL, WT, WR, WB = work_area()
SW, SH = _u.GetSystemMetrics(0), _u.GetSystemMetrics(1)
NEW_EXP = (WR - 150, WB - 150)
OLD_EXP = (SW - 150, SH - 150)

print("DPI=%s  工作区=(%d,%d)-(%d,%d)  主屏=%dx%d" % (DPI, WL, WT, WR, WB, SW, SH))
print("期望：新逻辑(工作区) = %s   旧逻辑(整屏) = %s" % (NEW_EXP, OLD_EXP))
print()

# hwnd -> (first_t, l, t, w, h, visible, class, title)
seen = {}
t0 = time.time()
while time.time() - t0 < DUR:
    now = time.time() - t0

    def cb(h, _l):
        if int(h) in seen:
            return True
        r = wintypes.RECT()
        _u.GetWindowRect(h, ctypes.byref(r))
        w, hh = r.right - r.left, r.bottom - r.top
        if w <= 0 or hh <= 0:
            return True
        n = _u.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(n + 2)
        _u.GetWindowTextW(h, b, n + 2)
        c = ctypes.create_unicode_buffer(256)
        _u.GetClassNameW(h, c, 256)
        seen[int(h)] = (now, r.left, r.top, w, hh, bool(_u.IsWindowVisible(h)), c.value, b.value)
        return True

    _u.EnumWindows(CB(cb), 0)

    # pid 过滤：只留桌宠进程的窗口
    for h in list(seen):
        d = wintypes.DWORD()
        _u.GetWindowThreadProcessId(wintypes.HWND(h), ctypes.byref(d))
        seen[h] = seen[h] + (d.value,)

    time.sleep(PERIOD)

rows = [v for v in seen.values() if len(v) > 8]
pids = {}
for v in rows:
    pids[v[8]] = pids.get(v[8], 0) + 1
print("涉及的 pid / 窗口数：", pids)
print()
print("%8s %10s %6s %5s %5s %8s %-30s %s" % ("t_ms", "hwnd", "left", "top", "w", "h", "class", "title"))
for h, v in sorted(rows, key=lambda kv: kv[1][0]):
    t, l, tp, w, hh, vis, cl, ti, pid = v
    mark = ""
    if abs(l - NEW_EXP[0]) <= 3 and abs(tp - NEW_EXP[1]) <= 3:
        mark = "   <== **命中『新逻辑(工作区)』期望**"
    elif abs(l - OLD_EXP[0]) <= 3 and abs(tp - OLD_EXP[1]) <= 3:
        mark = "   <== **命中『旧逻辑(整屏)』期望**"
    print("%8.0f %10d %6d %5d %5d %8s %-30s %s%s" % (t * 1000, h, l, tp, w, hh, vis, cl, ti, mark))

print()
hit_new = [h for h, v in rows if abs(v[1] - NEW_EXP[0]) <= 3 and abs(v[2] - NEW_EXP[1]) <= 3]
hit_old = [h for h, v in rows if abs(v[1] - OLD_EXP[0]) <= 3 and abs(v[2] - OLD_EXP[1]) <= 3]
print("首帧命中『新逻辑(工作区)』的窗口 =", hit_new)
print("首帧命中『旧逻辑(整屏)』的窗口 =", hit_old)
print("[DONE]")
