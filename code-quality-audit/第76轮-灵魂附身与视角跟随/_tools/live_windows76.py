"""真机验证：灵魂窗口是否真的出现（第76轮 R2/R3 硬判据）。

★ 必须先声明 DPI 感知，否则 GetWindowRect 会按缩放比缩小（铁律）。
"""
import ctypes
import ctypes.wintypes as wt
import io
import json
import os
import sys
import time

# ★★ 先声明 DPI 感知（PerMonitorV2）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

u32 = ctypes.windll.user32
EnumWindows = u32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

out_lines = []


def w(s=''):
    out_lines.append(s)
    try:
        print(s)
    except Exception:
        pass


def enum_visible():
    res = []

    def cb(hwnd, lparam):
        if not u32.IsWindowVisible(hwnd):
            return True
        n = u32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value
        rect = wt.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(rect))
        cls = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(hwnd, cls, 256)
        res.append({
            'hwnd': int(hwnd), 'title': title, 'cls': cls.value,
            'rect': [rect.left, rect.top, rect.right, rect.bottom],
            'w': rect.right - rect.left, 'h': rect.bottom - rect.top,
        })
        return True

    EnumWindows(EnumWindowsProc(cb), 0)
    return res


targets_kw = ['ralsei', 'soul', '灵魂', 'pet', '心']
w('=== 第76轮 真机窗口取证 ===')
w('时间 = %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
w()
wins = enum_visible()
w('可见顶层窗口共 %d 个' % len(wins))
w()
w('## 命中关键词的窗口')
hit = []
for x in wins:
    low = (x['title'] + ' ' + x['cls']).lower()
    if any(k.lower() in low for k in targets_kw):
        hit.append(x)
        w('  标题=%r 类=%r 矩形=%s 尺寸=%dx%d' % (x['title'], x['cls'], x['rect'], x['w'], x['h']))
if not hit:
    w('  （无）')
w()

w('## 全部窗口清单（前 60）')
for x in wins[:60]:
    w('  %-40r %-30r %dx%d @%s' % (x['title'][:38], x['cls'][:28], x['w'], x['h'], x['rect'][:2]))
w()

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   '_evidence', 'live_windows76.txt')
os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(out_lines))
print('written:', OUT)
