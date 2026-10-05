# -*- coding: utf-8 -*-
u"""第90轮续：**决定性实验** —— Qt 的 hide() / setWindowFlags() 会不会
**销毁原生窗口（HWND）**？

背景：真机日志出现 `MoveWindow … 无效的窗口句柄`，且实测宠物进程存活
（1 线程 / 0% CPU）但**全系统零个属于它的顶层窗口** ⇒ 宠物"人间蒸发"。
两种嫌疑：
  · `self.hide()`（托盘隐藏）在 Qt 上会 `destroy()` 原生窗口；
  · `setWindowFlags(...)` 在运行时调用会重建原生窗口。

做法：造一个**与桌宠同款 flags**（FramelessWindowHint | Tool + 透明背景）
的小窗口，按 show → hide → show → setWindowFlags 四步走，每步后用
 EnumWindows 数本进程的顶层窗口。纯本地、零依赖、不碰产品代码。

用法：python qt_winlife90.py
"""
import ctypes
import os
import sys
from ctypes import wintypes

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QWidget

user32 = ctypes.WinDLL('user32', use_last_error=True)
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [CB, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindow.argtypes = [wintypes.HWND]


def hwnds_of_pid(pid):
    out = []

    @CB
    def cb(h, l):
        d = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(d))
        if d.value == pid:
            out.append(int(h))
        return True

    user32.EnumWindows(cb, 0)
    return out


def main():
    app = QApplication(sys.argv)
    pid = os.getpid()
    w = QWidget()
    w.setWindowTitle('Probe90WinLife')
    w.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
    w.setAttribute(Qt.WA_TranslucentBackground, True)
    w.setGeometry(100, 100, 60, 60)

    steps = []
    log = []

    def snap(tag):
        hs = hwnds_of_pid(pid)
        alive = [h for h in hs if user32.IsWindow(h)]
        wid = -1
        try:
            wid = int(w.winId())
        except Exception:
            pass
        log.append('%-22s isVisible=%-5s winId=%-10d 本进程顶层窗口=%s 全部仍有效=%s'
                   % (tag, w.isVisible(), wid, hs, alive))
        return hs

    def step1():
        w.show()
        app.processEvents()
        snap('① show() 后')

    def step2():
        w.hide()
        app.processEvents()
        snap('② hide() 后')

    def step3():
        w.show()
        app.processEvents()
        snap('③ 再次 show() 后')

    def step4():
        w.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        app.processEvents()
        snap('④ setWindowFlags 后')
        w.show()
        app.processEvents()
        snap('⑤ setWindowFlags+show 后')

    def finish():
        print('=' * 78)
        print('Qt hide()/setWindowFlags() 对原生窗口（HWND）的影响')
        print('=' * 78)
        for l in log:
            print(l)
        print('-' * 78)
        print('结论：若 ② hide() 后"本进程顶层窗口=[]"⇒ hide() 会销毁 HWND（宠物会消失）')
        print('      若 ④ setWindowFlags 后 winId 变化 ⇒ 会重建 HWND（未 show 则不可见）')
        app.quit()

    QTimer.singleShot(300, step1)
    QTimer.singleShot(600, step2)
    QTimer.singleShot(900, step3)
    QTimer.singleShot(1200, step4)
    QTimer.singleShot(1500, finish)
    return app.exec_()


if __name__ == '__main__':
    raise SystemExit(main())
