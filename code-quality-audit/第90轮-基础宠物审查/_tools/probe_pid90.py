# -*- coding: utf-8 -*-
u"""第90轮续：按 pid 枚举**全部**顶层窗口（含不可见 / 最小化 / 无标题），
用于确认桌宠窗口当前到底是"藏在哪"。
用法：python probe_pid90.py [pid]
"""
import ctypes
import sys
from ctypes import wintypes

try:
    import psutil
except ImportError:
    psutil = None

user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(
    ctypes.c_bool, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
GWL_EXSTYLE = -20
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]

WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000


def title_of(h):
    n = user32.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 2)
    user32.GetWindowTextW(h, buf, n + 2)
    return buf.value


def class_of(h):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, buf, 256)
    return buf.value


def rect_of(h):
    r = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def main():
    targets = set()
    if len(sys.argv) > 1:
        targets.add(int(sys.argv[1]))
    else:
        # 自动找所有 python.exe
        if psutil:
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    if (p.info['name'] or '').lower().startswith('python'):
                        targets.add(p.info['pid'])
                except Exception:
                    pass

    print('目标 pid: %s' % sorted(targets))
    rows = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if targets and pid.value not in targets:
            return True
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        rows.append({
            'hwnd': int(hwnd),
            'pid': pid.value,
            'cls': class_of(hwnd),
            'title': title_of(hwnd),
            'rect': rect_of(hwnd),
            'visible': bool(user32.IsWindowVisible(hwnd)),
            'iconic': bool(user32.IsIconic(hwnd)),
            'toolwindow': bool(ex & WS_EX_TOOLWINDOW),
            'layered': bool(ex & WS_EX_LAYERED),
        })
        return True

    user32.EnumWindows(cb, 0)
    print('命中 %d 个顶层窗口：' % len(rows))
    for r in sorted(rows, key=lambda x: -(x['rect'][2] * x['rect'][3])):
        l, t, w, h = r['rect']
        print('hwnd=%-10d pid=%-6d vis=%-5s iconic=%-5s tool=%-5s layered=%-5s rect=%d,%d,%dx%d cls=%s title=%r'
              % (r['hwnd'], r['pid'], r['visible'], r['iconic'], r['toolwindow'],
                 r['layered'], l, t, w, h, r['cls'], r['title']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
