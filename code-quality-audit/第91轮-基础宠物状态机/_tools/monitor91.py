# -*- coding: utf-8 -*-
u"""第91轮：**全程屏幕监控** —— 盯住桌宠窗口 + 按窗口矩形逐帧裁剪取证。

为什么这么做（第90轮踩过的坑）
------------------------------
  · 桌宠是**透明分层窗口**（`Qt.FramelessWindowHint | Qt.Tool` + `WA_TranslucentBackground`）。
    `PrintWindow` 对这类窗口只能抓到 ~1% 的精灵像素（背景全黑），
    所以**取证必须走"整屏 GDI 截图 + 按窗口矩形裁剪"**——那才是人眼看到的画面。
  · 屏幕工具报的"可见面积/OCR"对透明窗口不可信，但**几何（矩形）是准的**
    ⇒ 位置/运动用 Win32 矩形判定，外观用裁剪图判定（两条独立的判据）。
  · 必须先声明 **DPI 感知**，否则矩形是 DWM 缩放后的假坐标。

用法：
  python monitor91.py --seconds 420 --outdir <ASCII路径> [--pid N] [--fps 4] [--shot-every 2]
产物：<outdir>/timeline.tsv（每次采样的矩形）· <outdir>/f0001.png …（裁剪帧）
"""
import argparse
import ctypes
import os
import time
from ctypes import wintypes

import numpy as np
import cv2

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [CB, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
SRCCOPY = 0x00CC0020


class BMIH(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


class BMI(ctypes.Structure):
    _fields_ = [('bmiHeader', BMIH), ('bmiColors', wintypes.DWORD * 3)]


user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         ctypes.c_int, wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.POINTER(BMI), wintypes.UINT]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]


def grab(x, y, w, h):
    hdc = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, w, h, hdc, x, y, SRCCOPY)
    bi = BMI()
    bi.bmiHeader.biSize = ctypes.sizeof(BMIH)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(0, hdc)
    return np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)[:, :, :3].copy()


def gtitle(h):
    n = user32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 2)
    user32.GetWindowTextW(h, b, n + 2)
    return b.value


def gclass(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, b, 256)
    return b.value


def find_pet(pid=None):
    """返回 (hwnd, rect, visible, iconic, title, cls)；找不到返回 None。"""
    best = [None]

    @CB
    def cb(h, l):
        if not user32.IsWindow(h):
            return True
        d = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(d))
        t = gtitle(h)
        c = gclass(h)
        ok_pid = (pid is not None and d.value == pid)
        ok_title = ('ralsei' in t.lower())
        if not (ok_pid or ok_title):
            return True
        r = wintypes.RECT()
        user32.GetWindowRect(h, ctypes.byref(r))
        area = max(0, r.right - r.left) * max(0, r.bottom - r.top)
        if best[0] is None or area > best[0][0]:
            best[0] = (area, int(h), (r.left, r.top, r.right - r.left, r.bottom - r.top),
                       bool(user32.IsWindowVisible(h)), bool(user32.IsIconic(h)), t, c,
                       d.value)
        return True

    user32.EnumWindows(cb, 0)
    return best[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=420.0)
    ap.add_argument('--outdir', default=r'C:\Users\23002\Downloads\_tmp\mon91')
    ap.add_argument('--pid', type=int, default=None)
    ap.add_argument('--fps', type=float, default=4.0)
    ap.add_argument('--shot-every', type=float, default=2.0)
    ap.add_argument('--margin', type=int, default=60)
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    ts_path = os.path.join(a.outdir, 'timeline.tsv')
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    print('虚拟屏 (%d,%d) %dx%d   监控 %.0fs @%.1fHz   产物=%s'
          % (vx, vy, vw, vh, a.seconds, a.fps, a.outdir))

    t0 = time.time()
    n = 0
    n_shot = 0
    lost = 0
    with open(ts_path, 'w', encoding='utf-8') as fh:
        fh.write('t\thwnd\tpid\tvisible\ticonic\tleft\ttop\tw\th\tclass\ttitle\n')
        last_shot = -1e9
        while time.time() - t0 < a.seconds:
            n += 1
            now = time.time()
            got = find_pet(a.pid)
            if got is None:
                lost += 1
                fh.write('%.3f\t-\t-\t-\t-\t-\t-\t-\t-\t-\t<窗口不存在>\n' % (now - t0))
            else:
                _area, h, (l, t, w, hh), vis, ico, ti, cl, pd = got
                fh.write('%.3f\t%d\t%d\t%s\t%s\t%d\t%d\t%d\t%d\t%s\t%s\n'
                         % (now - t0, h, pd, vis, ico, l, t, w, hh, cl, ti))
                if now - last_shot >= a.shot_every:
                    last_shot = now
                    cx = max(vx, l - a.margin)
                    cy = max(vy, t - a.margin)
                    cw = min(vx + vw, l + w + a.margin) - cx
                    ch = min(vy + vh, t + hh + a.margin) - cy
                    if cw > 4 and ch > 4:
                        img = grab(cx, cy, cw, ch)
                        n_shot += 1
                        # 放大 2 倍便于人眼确认精灵
                        big = cv2.resize(img, (cw * 2, ch * 2), interpolation=cv2.INTER_NEAREST)
                        cv2.imencode('.png', big)[1].tofile(
                            os.path.join(a.outdir, 'f%04d.png' % n_shot))
            time.sleep(max(0.0, 1.0 / a.fps - (time.time() - now)))

    print('采样 %d 次 · 裁剪帧 %d 张 · 窗口不存在 %d 次' % (n, n_shot, lost))
    print('timeline = %s' % ts_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
