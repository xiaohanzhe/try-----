# -*- coding: utf-8 -*-
u"""第90轮 · 真机 z 序对账：宠物在墙纸之前还是之后？（只读）

Win32 语义确认：SetWindowPos(hwnd, hWndInsertAfter, …) 里
`hWndInsertAfter` = **排在 hwnd 前面**（更靠上）的那个窗口。
"""
import ctypes
import sys

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

import win32gui

GW_HWNDNEXT = 2
PID = int(sys.argv[1]) if len(sys.argv) > 1 else None


def all_top():
    out = []
    h = win32gui.GetTopWindow(0)
    seen = set()
    while h and h not in seen:
        seen.add(h)
        out.append(h)
        h = win32gui.GetWindow(h, GW_HWNDNEXT)
    return out


def pid_of(h):
    p = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


tops = all_top()
idx = {h: i for i, h in enumerate(tops)}
print('顶层窗口数 =', len(tops))


def info(tag, h):
    if not h:
        print('  %-24s (无)' % tag)
        return
    try:
        cls = win32gui.GetClassName(h)
    except Exception:
        cls = '?'
    try:
        txt = win32gui.GetWindowText(h)
    except Exception:
        txt = ''
    print('  %-24s hwnd=0x%08X  z=%-5s  vis=%-5s  %-24s %r'
          % (tag, h, idx.get(h, '-'), win32gui.IsWindowVisible(h), cls, txt[:24]))


progman = win32gui.FindWindow('Progman', None)
workerw0 = win32gui.FindWindowEx(0, 0, 'WorkerW', None)
hosts = [h for h in tops
         if win32gui.FindWindowEx(h, 0, 'SHELLDLL_DefView', None)]

print()
info('Progman', progman)
info('WorkerW(FindWindowEx 0)', workerw0)
for i, h in enumerate(hosts):
    info('SHELLDLL_DefView 宿主#%d' % i, h)
if hosts:
    info('宿主之后的 WorkerW', win32gui.FindWindowEx(0, hosts[0], 'WorkerW', None))

pets = [h for h in tops if pid_of(h) == PID] if PID else []
print()
print('宠物窗口 z 序位置：')
for i, h in enumerate(pets):
    info('PET#%d' % i, h)
    r = win32gui.GetWindowRect(h)
    cx, cy = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
    wh = win32gui.WindowFromPoint((cx, cy))
    print('      rect=%s center=(%d,%d)' % (r, cx, cy))
    print('      该点最前窗口 = 0x%08X (%s)  ⇒ 是宠物本体: %s'
          % (wh, win32gui.GetClassName(wh) if wh else '-', wh == h))

print()
print('判读：z 数字越小越靠前（越靠近用户）。')
print('      若宠物 z 介于「SHELLDLL 宿主」与「宿主之后的 WorkerW」之间或更大，')
print('      说明宠物被插到了墙纸层之后 → 屏幕上根本看不见（除非抓屏工具看不见分层窗口）。')
