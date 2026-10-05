# -*- coding: utf-8 -*-
"""第91轮：用 PrintWindow(PW_RENDERFULLCONTENT) 抓窗口**自身内容**（不受遮挡影响）。

为什么要换这条路：
  · BitBlt 从屏幕 DC 抓屏，在 DWM 合成下可能拿不到**透明分层窗口**的像素；
    而且桌宠不置顶，前台全屏窗口会把它盖住 ⇒ 整屏抓到的根本不是宠物。
  · PrintWindow 让**窗口自己**把内容画到我们给的 DC 上，与 z 序无关。
    PW_RENDERFULLCONTENT(2) 是给 DirectComposition/分层窗口用的。
本脚本同时对同一 hwnd 跑 BitBlt 与 PrintWindow 两条路做**交叉对照**。
"""
import ctypes
import os
import sys
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import monitor91 as M  # noqa: E402
import cv2  # noqa: E402
import numpy as np  # noqa: E402

u, g = M.user32, M.gdi32
u.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
PW_RENDERFULLCONTENT = 2


def print_window(hwnd, w, h):
    hdc = u.GetDC(0)
    mem = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    g.SelectObject(mem, bmp)
    ok = u.PrintWindow(hwnd, mem, PW_RENDERFULLCONTENT)
    bi = M.BMI()
    bi.bmiHeader.biSize = ctypes.sizeof(M.BMIH)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
    g.DeleteObject(bmp)
    g.DeleteDC(mem)
    u.ReleaseDC(0, hdc)
    return ok, np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)[:, :, :3].copy()


PID = int(sys.argv[1]) if len(sys.argv) > 1 else 4712
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
wins = []


def cb(h, l):
    d = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(d))
    if d.value == PID and u.IsWindowVisible(h):
        r = wintypes.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        w, hh = r.right - r.left, r.bottom - r.top
        if 15 <= w <= 80 and 40 <= hh <= 110:
            wins.append((int(h), r.left, r.top, w, hh))
    return True


u.EnumWindows(CB(cb), 0)
OUTD = r'C:\Users\23002\Downloads\_tmp'
print('宠物本体候选: %s' % wins)
for i, (hwnd, l, t, w, hh) in enumerate(wins):
    ok, img = print_window(hwnd, w, hh)
    nz = int((img.sum(axis=2) > 8).sum())
    big = cv2.resize(img, (w * 6, hh * 6), interpolation=cv2.INTER_NEAREST)
    p = os.path.join(OUTD, 'pw91_%d_%dx%d_at%d_%d.png' % (i, w, hh, l, t))
    cv2.imencode('.png', big)[1].tofile(p)
    print('  #%d hwnd=%d PrintWindow ok=%s 非黑像素=%d/%d -> %s'
          % (i, hwnd, ok, nz, w * hh, os.path.basename(p)))
