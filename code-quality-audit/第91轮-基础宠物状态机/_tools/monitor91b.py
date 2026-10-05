# -*- coding: utf-8 -*-
"""第91轮（修正版）：全程监控桌宠本体。

修掉原版 monitor91.py 的两个缺陷（都是实机抓出来的）：
  ① `find_pet` 取"面积最大的匹配窗口" ⇒ 抓到的是**对话框**(620x255，不动)。
     修正：用形状判据 —— 宠物本体是**竖长条**（h > w）且尺寸 20..80 x 40..110，
     这样自动排除对话框(620x255)与灵魂(48x48 正方形)。
  ② 截图用"整屏 BitBlt 后按矩形裁剪" ⇒ 桌宠**不置顶**，前台全屏窗口会盖住它，
     抓到的其实是别人的 UI。修正：用 **PrintWindow(PW_RENDERFULLCONTENT)** 让
     窗口自己渲染，与 z 序无关（实测非黑像素 62%，对应 GDI 路线只有 ~1%）。

另外每次采样额外记 `occluded`：用 `WindowFromPoint(窗口中心)` 判断该窗口
当前是不是**屏幕上真正可见的那个** —— 这就是「宠物被人看不见」的硬判据。
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
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.GetDC.argtypes = [wintypes.HWND]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
PW_RENDERFULLCONTENT = 2


class BMIH(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


class BMI(ctypes.Structure):
    _fields_ = [('bmiHeader', BMIH), ('bmiColors', wintypes.DWORD * 3)]


def print_window(hwnd, w, h):
    hdc = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(hwnd, mem, PW_RENDERFULLCONTENT)
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
    return ok, np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)[:, :, :3].copy()


def find_body(pid):
    """宠物本体：pid 匹配 + 可见 + 竖长条(h>w) + 尺寸窗。返回 (hwnd,l,t,w,h,occluded)。"""
    best = [None]

    @CB
    def cb(h, l):
        if not user32.IsWindow(h):
            return True
        d = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(d))
        if d.value != pid or not user32.IsWindowVisible(h):
            return True
        r = wintypes.RECT()
        user32.GetWindowRect(h, ctypes.byref(r))
        w, hh = r.right - r.left, r.bottom - r.top
        if not (hh > w and 18 <= w <= 90 and 38 <= hh <= 120):
            return True
        area = w * hh
        if best[0] is None or area > best[0][5]:
            pt = wintypes.POINT()
            pt.x, pt.y = r.left + w // 2, r.top + hh // 2
            top = user32.WindowFromPoint(pt)
            occl = (int(top) != int(h))
            best[0] = (int(h), r.left, r.top, w, hh, area, occl)
        return True

    user32.EnumWindows(cb, 0)
    return best[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=420.0)
    ap.add_argument('--outdir', default=r'C:\Users\23002\Downloads\_tmp\mon91b')
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--fps', type=float, default=4.0)
    ap.add_argument('--shot-every', type=float, default=2.0)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    ts_path = os.path.join(a.outdir, 'timeline.tsv')
    print('监控 %.0fs @%.1fHz pid=%d -> %s' % (a.seconds, a.fps, a.pid, a.outdir))

    t0, n, nshot, lost = time.time(), 0, 0, 0
    with open(ts_path, 'w', encoding='utf-8') as fh:
        fh.write('t\thwnd\tleft\ttop\tw\th\toccluded\n')
        last = -1e9
        while time.time() - t0 < a.seconds:
            n += 1
            now = time.time()
            got = find_body(a.pid)
            if got is None:
                lost += 1
                fh.write('%.3f\t-\t-\t-\t-\t-\t-\n' % (now - t0))
            else:
                hwnd, l, t, w, hh, area, occl = got
                fh.write('%.3f\t%d\t%d\t%d\t%d\t%d\t%s\n' % (now - t0, hwnd, l, t, w, hh, occl))
                if now - last >= a.shot_every:
                    last = now
                    ok, img = print_window(hwnd, w, hh)
                    nshot += 1
                    big = cv2.resize(img, (w * 5, hh * 5), interpolation=cv2.INTER_NEAREST)
                    cv2.imencode('.png', big)[1].tofile(
                        os.path.join(a.outdir, 'f%04d.png' % nshot))
            time.sleep(max(0.0, 1.0 / a.fps - (time.time() - now)))
    print('采样 %d · 抓帧 %d · 窗口不存在 %d' % (n, nshot, lost))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
