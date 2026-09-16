# -*- coding: utf-8 -*-
"""第十三轮临时探针（不入库）：宠物坐标系到底是"物理像素"还是"逻辑/DIP"？

背景：真机探针发现 `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS)` 返回的矩形
是 `win32gui.GetWindowRect` 的 1.5 倍（本机 150% 缩放）。这两者一个物理、一个被
DPI 虚拟化 —— 如果宠物（Qt）活在逻辑坐标系里，那把楼层矩形换成 DWM 物理值就会让
"楼板"和"宠物"变成两套单位，运动/遮挡全部错位。必须在真机上把这一点钉死。
"""
import ctypes
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PET = os.path.join(BASE, 'ralsei_pet')
for _p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

import win32api                                              # noqa: E402
import win32gui                                              # noqa: E402
from PyQt5.QtWidgets import QApplication                     # noqa: E402

import desktop_interaction as DI                             # noqa: E402

OUT = []


def say(s=''):
    OUT.append(str(s))


say('=== A 各口径下的"屏幕尺寸"（谁是物理、谁是逻辑）===')
user32 = ctypes.windll.user32
say('ctypes user32.GetSystemMetrics(0,1) 屏幕     : %s x %s'
    % (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)))
say('ctypes GetSystemMetrics(76..79) 虚拟桌面     : %s x %s'
    % (user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)))
say('win32api.GetSystemMetrics(0,1)               : %s x %s'
    % (win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)))
try:
    import win32con
    say('win32api DESKTOPHORZRES(118) / 物理          : %s x %s'
        % (win32api.GetSystemMetrics(118), win32api.GetSystemMetrics(119)))
except Exception as e:
    say('DESKTOPHORZRES 取不到: %s' % e)

app = QApplication(sys.argv)
say('Qt primaryScreen().geometry()               : %s x %s'
    % (app.primaryScreen().geometry().width(), app.primaryScreen().geometry().height()))
say('Qt virtualGeometry()                         : %s x %s'
    % (app.primaryScreen().virtualGeometry().width(),
       app.primaryScreen().virtualGeometry().height()))
say('Qt availableGeometry()                       : %s x %s'
    % (app.primaryScreen().availableGeometry().width(),
       app.primaryScreen().availableGeometry().height()))
say('Qt devicePixelRatio()                        : %s' % app.primaryScreen().devicePixelRatio())
say('QApplication.desktop().availableGeometry()   : %s x %s'
    % (app.desktop().availableGeometry().width(),
       app.desktop().availableGeometry().height()))

say()
say('=== B 同一个真实窗口，三种取矩形口径对比 ===')
fg = win32gui.GetForegroundWindow()
try:
    say('前台窗口 title = %r' % win32gui.GetWindowText(fg))
except Exception:
    pass


def _ctypes_get_window_rect(h):
    class _R(ctypes.Structure):
        _fields_ = [('l', ctypes.c_long), ('t', ctypes.c_long),
                    ('r', ctypes.c_long), ('b', ctypes.c_long)]
    r = _R()
    user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_R)]
    user32.GetWindowRect.restype = ctypes.c_int
    user32.GetWindowRect(ctypes.c_void_p(h), ctypes.byref(r))
    return (r.l, r.t, r.r, r.b)


say('1) win32gui.GetWindowRect      : %s' % (win32gui.GetWindowRect(fg),))
say('2) ctypes user32.GetWindowRect : %s' % (_ctypes_get_window_rect(fg),))
say('3) DWM EXTENDED_FRAME (本项目的) : %s' % (DI.get_frame_rect(fg),))
say()
say('判断法：宠物（Qt）若与 1)/2) 同量纲 → DWM(3) 是"异类"，本轮改动方向反了；')
say('        若 Qt 与 3) 同量纲 → DWM 才是对的，老代码用 GetWindowRect 一直是错位。')

try:
    _dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(_dir, '_out_dpi.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(OUT))
except Exception:
    pass
print('\n'.join(OUT))
