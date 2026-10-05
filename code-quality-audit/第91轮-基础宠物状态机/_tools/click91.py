# -*- coding: utf-8 -*-
"""第91轮：点击宠物（唤醒）后它会不会动？ —— 区分「宠物坏了」与「宠物只是睡了/不自主走」。

当日日志的既有判据：「单击一次宠物 ⇒ 25s 内 7 次位移」。
本脚本：找到宠物本体窗口中心 → 左键单击 → 报告点击坐标；随后由 monitor91b 采轨迹。
鼠标位置**用后还原**，减少打扰。
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import monitor91b as MB  # noqa: E402

u = MB.user32
PID = int(sys.argv[1]) if len(sys.argv) > 1 else 4712

got = MB.find_body(PID)
if got is None:
    print('★ 找不到宠物本体窗口')
    raise SystemExit(1)
hwnd, l, t, w, h, area, occl = got
cx, cy = l + w // 2, t + h // 2
print('宠物本体 hwnd=%d rect=(%d,%d %dx%d) 中心=(%d,%d) occluded=%s'
      % (hwnd, l, t, w, h, cx, cy, occl))

save = wintypes.POINT()
u.GetCursorPos(ctypes.byref(save))
u.SetCursorPos(cx, cy)
time.sleep(0.12)
u.mouse_event(0x0002, 0, 0, 0, 0)
time.sleep(0.06)
u.mouse_event(0x0004, 0, 0, 0, 0)
print('已在 (%d,%d) 左键单击一次' % (cx, cy))
time.sleep(0.05)
u.SetCursorPos(save.x, save.y)
print('鼠标已还原到 (%d,%d)' % (save.x, save.y))
