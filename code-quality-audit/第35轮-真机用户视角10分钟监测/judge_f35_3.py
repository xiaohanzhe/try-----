# -*- coding: utf-8 -*-
"""第 35 轮 —— F35-3 判定：在**产品进程内**读 GetSystemMetrics，看 clamp 是否失效。

背景：
    纯 Python 进程 IsProcessDPIAware()=False => GetSystemMetrics 返回逻辑像素 1707x1067
    （本机缩放 150%，2560/1.5=1707）。
    产品是 PyQt5 应用，Qt 会设置进程 DPI 感知，**因此产品进程内的读数可能不同**。
    `_virtual_screen_rect()` 只在**产品进程内**执行 ⇒ 必须在同一上下文里测，否则
    又是一次"判据失真"。

本脚本就在产品上下文（QApplication 已建）内读这几个值。
"""
import os
import sys
import ctypes

WS = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
EV = os.path.join(WS, "code-quality-audit", "第35轮-真机用户视角10分钟监测", "_evidence")
sys.path.insert(0, os.path.join(WS, "ralsei_pet", "src"))
sys.path.insert(0, os.path.join(WS, "ralsei_pet"))

from PyQt5.QtWidgets import QApplication

app = QApplication(sys.argv)

import win32api

u = ctypes.windll.user32
L = []
L.append("F35-3 判定：产品进程（QApplication 已建）内的 GetSystemMetrics")
L.append("=" * 66)
L.append("python 版本: %s" % sys.version.split()[0])
L.append("")
L.append("【DPI 感知状态】")
L.append("  IsProcessDPIAware() = %s" % bool(u.IsProcessDPIAware()))
try:
    L.append("  GetDpiForSystem()   = %s" % u.GetDpiForSystem())
except Exception as e:
    L.append("  GetDpiForSystem err: %s" % e)
L.append("")
L.append("【win32 读数（产品进程内）】")
L.append("  SM_CXSCREEN        = %d" % win32api.GetSystemMetrics(0))
L.append("  SM_CYSCREEN        = %d" % win32api.GetSystemMetrics(1))
L.append("  SM_CXVIRTUALSCREEN = %d" % win32api.GetSystemMetrics(78))
L.append("  SM_CYVIRTUALSCREEN = %d" % win32api.GetSystemMetrics(79))
L.append("")
L.append("【Qt 读数（产品进程内）】")
s = app.primaryScreen()
L.append("  geometry()          = %s" % s.geometry())
L.append("  virtualGeometry()   = %s" % s.virtualGeometry())
L.append("  availableGeometry() = %s" % s.availableGeometry())
L.append("  devicePixelRatio()  = %s" % s.devicePixelRatio())
L.append("")

# 关键：产品 _virtual_screen_rect 用的正是 win32 值
wx, wy = win32api.GetSystemMetrics(76), win32api.GetSystemMetrics(77)
ww, wh = win32api.GetSystemMetrics(78), win32api.GetSystemMetrics(79)
qg = s.geometry()
L.append("【clamp 上界对比】")
L.append("  _virtual_screen_rect() 将返回 (%d,%d,%d,%d)" % (wx, wy, ww, wh))
L.append("  Qt screenGeometry()        = (%d,%d,%d,%d)"
         % (qg.x(), qg.y(), qg.width(), qg.height()))
same = (wx, wy, ww, wh) == (qg.x(), qg.y(), qg.width(), qg.height())
L.append("  两者一致? %s" % same)
L.append("")
if same:
    L.append("⇒ **F35-3 撤销**：产品进程内 win32 与 Qt 坐标系一致，clamp 上界正确。")
    L.append("  之前观察到的 1707x1067 来自**非 DPI 感知的辅助进程**，不适用于产品。")
else:
    L.append("⇒ **F35-3 成立**：产品进程内两者仍不一致 => clamp 上界错误，宠物可越界。")

dst = os.path.join(EV, "41_F35-3判定_产品进程内读数.txt")
open(dst, "w", encoding="utf-8").write("\n".join(L))
print("\n".join(L))
print()
print("WROTE", dst)
