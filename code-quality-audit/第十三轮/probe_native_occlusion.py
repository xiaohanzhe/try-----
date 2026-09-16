# -*- coding: utf-8 -*-
"""第十三轮真机探针：在**真实桌面**上核验新的 Windows 原生口径与遮挡模型。

与回归套件的分工：
  · verify_round13_build.py —— 合成窗口表，结果确定可复现（门禁用）；
  · 本探针 —— 真实窗口，输出随桌面现状变化（**证据**用，不入 G2）。

核验四件事：
 1. DWM 可见边框 vs GetWindowRect：差额就是 DWM 不可见阴影（楼板"必须和窗口一模一样"）。
 2. 幽灵窗口（DWMWA_CLOAKED）/ 工具窗 / 本进程窗口被过滤掉的**数量**。
 3. 原生 `WindowFromPoint`：屏幕中心点上"最上面是谁"，是否与前台窗口一致。
 4. 用真实窗口表建楼层：每层的可见面积占比（"被压下去的不存在"是否符合直觉）。
"""
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PET = os.path.join(BASE, 'ralsei_pet')
for _p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

import win32api                                              # noqa: E402
import win32gui                                              # noqa: E402
from PyQt5.QtCore import QRect, QPoint                       # noqa: E402
from PyQt5.QtWidgets import QApplication                     # noqa: E402

# ⚠ 必须先建 QApplication 再读任何坐标（第十三轮踩坑记录）
# ---------------------------------------------------------------------------
# Qt 在创建 QApplication 时会把进程 DPI 感知级别设成 per-monitor v2。在此之前进程是
# **DPI 不感知**的，于是 `GetWindowRect` / `GetSystemMetrics` 会被 Windows 按系统缩放
# 虚拟化（本机 150%：物理 2560x1600 → 回报 1707x1067），而
# `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS)` **永远返回物理像素**。
# 两者混用会得到"DWM 矩形正好是 GetWindowRect 的 1.5 倍"的假象（曾据此误判改动方向）。
# 真机宠物一定活在 QApplication 里 → 建完 app 后两个口径本来就一致。
_app = QApplication(sys.argv)

import desktop_interaction as DI                             # noqa: E402
import floor_manager as FM                                   # noqa: E402

OUT = []


def say(s=''):
    OUT.append(str(s))


say('=== 0) 量纲自检（QApplication 建好后各口径必须同量纲）===')
_qs = _app.primaryScreen().geometry()
say('Qt  primaryScreen().geometry() : %d x %d   devicePixelRatio=%s'
    % (_qs.width(), _qs.height(), _app.primaryScreen().devicePixelRatio()))
say('Qt  availableGeometry()        : %d x %d'
    % (_app.primaryScreen().availableGeometry().width(),
       _app.primaryScreen().availableGeometry().height()))
say('Win GetSystemMetrics(0,1)      : %d x %d'
    % (win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)))
say('→ 二者一致才说明"楼层坐标系 == 宠物坐标系"（第十三轮 DPI 陷阱）')

say()
say('=== 1) DWM 可见边框 vs GetWindowRect（阴影差额）===')
say('%-28s %-26s %-26s %s' % ('窗口标题', 'GetWindowRect', 'DWM 可见边框', '每边差额'))


def _top_windows():
    out = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h) and not win32gui.IsIconic(h):
            t = win32gui.GetWindowText(h)
            r = win32gui.GetWindowRect(h)
            if t and (r[2] - r[0]) > 100 and (r[3] - r[1]) > 100:
                out.append((h, t, r))
        return True

    try:
        win32gui.EnumWindows(cb, None)
    except Exception:
        pass
    return out


shown = 0
for hwnd, title, raw in _top_windows()[:8]:
    frame = DI.get_frame_rect(hwnd)
    inset = (frame[0] - raw[0], frame[1] - raw[1], raw[2] - frame[2], raw[3] - frame[3])
    say('%-28s %-26s %-26s %s' % (title[:26], str(raw), str(frame), inset))
    shown += 1
if not shown:
    say('（当前没有 ≥100x100 的可见窗口）')

say()
say('=== 2) 原生过滤器效果 ===')
raw_list = _top_windows()
cloaked = [t for h, t, _r in raw_list if DI.is_cloaked(h)]
tool = []
noact = []
import win32con                                              # noqa: E402
for h, t, _r in raw_list:
    try:
        ex = win32gui.GetWindowLong(h, win32con.GWL_EXSTYLE)
        if ex & win32con.WS_EX_TOOLWINDOW:
            tool.append(t)
        if ex & win32con.WS_EX_NOACTIVATE:
            noact.append(t)
    except Exception:
        pass
say('可见顶层窗口（粗筛，≥100x100 有标题）: %d' % len(raw_list))
say('  其中 DWM 幽灵窗口(cloaked): %d %s' % (len(cloaked), cloaked[:5]))
say('  其中 WS_EX_TOOLWINDOW     : %d %s' % (len(tool), tool[:5]))
say('  其中 WS_EX_NOACTIVATE     : %d %s' % (len(noact), noact[:5]))

say()
say('=== 3) 原生 WindowFromPoint（"这一点上最上面是谁"）===')
# 虚拟桌面矩形先读出来：section 4 也要用，且不能放在 try 里（失败会让 4 段 NameError）
vx = win32api.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
vy = win32api.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
vw = win32api.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
vh = win32api.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
try:
    cx, cy = vx + vw // 2, vy + vh // 2
    h_top = DI.window_from_point(cx, cy)
    fg = win32gui.GetForegroundWindow()
    say('虚拟桌面 = (%d,%d) %dx%d ；屏幕中心 = (%d,%d)' % (vx, vy, vw, vh, cx, cy))
    say('该点上最上面的窗口 hwnd=%s title=%r'
        % (h_top, win32gui.GetWindowText(h_top) if h_top else ''))
    say('当前前台窗口     hwnd=%s title=%r' % (fg, win32gui.GetWindowText(fg)))
    say('一致: %s（中心点上未必是前台窗口 —— 只说明 WindowFromPoint 命中的是"那一点上"的顶层窗口）'
        % (h_top == fg))
    say('该点所属进程 pid=%s；本进程 pid=%s（相等则说明打到的是自己 → 必须靠进程号排除）'
        % (DI.get_window_pid(h_top), os.getpid()))
except Exception as e:
    say('原生命中断言失败（已忽略）: %s' % e)

say()
say('=== 4) 用真实窗口表建楼层（**走产品真实的过滤枚举**）===')
say('（这里不用上面的粗筛 raw_list：粗筛只过滤"可见且不最小化"，不过滤幽灵/工具窗/自身，')
say('  用它建楼会高估楼层数。直接调产品方法 get_all_visible_windows 才是真口径。）')

_di = object.__new__(DI.DesktopInteraction)      # 绕开 __init__ 的重依赖（QTimer/桌面路径）
_di.parent = None
_di._visible_windows_cache = None
_di.privacy_apps = []
_di.user_opened_privacy_apps = set()
_di.desktop_path = ''
real_wins = DI.DesktopInteraction.get_all_visible_windows(_di, use_cache=False)

say('粗筛窗口数 = %d  →  产品过滤后 = %d  （被滤掉 %d：幽灵/工具窗/无激活/自身/出屏）'
    % (len(raw_list), len(real_wins), len(raw_list) - len(real_wins)))
for w in real_wins:
    say('  留下: hwnd=%-9s %r rect=%s' % (w['hwnd'], w.get('title', '')[:28], w['rect']))

fm = FM.FloorManager(parent=None)
fm.desktop_floor['rect'] = QRect(vx, vy, vw, vh)
# 用产品同款的 z 序（GetTopWindow + GW_HWNDNEXT）
order = {}
cur = win32gui.GetTopWindow(None)
i = 0
while cur:
    order[cur] = i
    cur = win32gui.GetWindow(cur, 2)
    i += 1

for w in real_wins:
    r = w['rect']
    fm.underlying_windows.append({
        'hwnd': w['hwnd'], 'title': w.get('title', ''), 'class_name': w.get('class_name', ''),
        'rect': QRect(r[0], r[1], r[2] - r[0], r[3] - r[1]),
        'z_order': order.get(w['hwnd'], 9999),
    })
fm._generate_floors()
say('窗口数 = %d → 有效楼层数 = %d（差额 = "被压下去暂时不存在"或可见面积太小）'
    % (len(fm.underlying_windows), len(fm.floors)))
for f in fm.floors[:12]:
    full = f['rect'].width() * f['rect'].height()
    ratio = (f['visible_area'] / full * 100.0) if full else 0.0
    say('  L%-3s hwnd=%-9s 可见 %5d/%5d px (%5.1f%%)  %s'
        % (f['platform_height'], f['window_hwnd'], f['visible_area'], full, ratio,
           f['window'].get('title', '')[:30]))

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_out_native.txt'),
          'w', encoding='utf-8') as fh:
    fh.write('\n'.join(OUT))
print('\n'.join(OUT))
