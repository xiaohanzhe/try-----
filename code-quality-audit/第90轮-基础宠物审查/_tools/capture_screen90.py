# -*- coding: utf-8 -*-
u"""第90轮续：GDI 截整屏（虚拟屏）→ 存 ASCII 路径，便于 Read 查看。
自带 DPI 感知声明（量桌宠/浮层的前置铁律）。
用法：python capture_screen90.py [out.png]
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

import numpy as np
import cv2

# ★ 先声明 DPI 感知，否则拿到的是被 DWM 缩放的假像素
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79

user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         ctypes.c_int, wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]

SRCCOPY = 0x00CC0020


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wintypes.DWORD * 3)]


def capture(x, y, w, h):
    hdc = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, w, h, hdc, x, y, SRCCOPY)

    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h            # 负 = 自上而下
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0        # BI_RGB
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
                                wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(BITMAPINFO),
                                wintypes.UINT]
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(0, hdc)

    arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
    return arr[:, :, :3].copy()


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\23002\Downloads\_tmp\screen90.png'
    x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    print('虚拟屏 = (%d,%d) %dx%d' % (x, y, w, h))
    t0 = time.time()
    img = capture(x, y, w, h)
    print('抓取耗时 %.2fs  shape=%s' % (time.time() - t0, img.shape))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv2.imencode('.png', img)[1].tofile(out)
    print('已写 -> %s (%d B)' % (out, os.path.getsize(out)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
