# -*- coding: utf-8 -*-
u"""按窗口句柄抓图（PrintWindow）—— 修 `grabWindow(0)` 抓不到透明分层窗口的问题。

★ 第89轮实测教训：
  `QScreen.grabWindow(0)`（全屏抓）在 Windows 上**抓不到带 WA_TranslucentBackground
  的分层窗口** —— 抓出来的图上只有壁纸和任务栏，桌宠/画布/对话框**一律不见**。
  差点据此误判"桌宠没上屏"（实际 `EnumWindows` 显示三个窗口 rect 全在屏内、
  IsWindowVisible 全 True）。
  ⇒ 这正是记忆里的铁律「**产物侧看不见 ≠ 调用侧没发生**」。
  改用 `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT=2)` 逐窗口抓。
"""
import ctypes
import os
import sys
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

u = ctypes.windll.user32
gdi = ctypes.windll.gdi32
EnumWindows = u.EnumWindows
P = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

HERE = os.path.abspath(os.path.dirname(__file__))
OUT = os.path.join(HERE, '..', '_evidence', 'shots')


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def pid_of(h):
    p = ctypes.c_ulong()
    u.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def ttl(h):
    n = u.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, b, n + 1)
    return b.value


def grab(h):
    r = RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    w, hh = r.right - r.left, r.bottom - r.top
    if w <= 0 or hh <= 0:
        return None, 0, 0
    hdc = u.GetWindowDC(h)
    mdc = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, w, hh)
    gdi.SelectObject(mdc, bmp)
    # PW_RENDERFULLCONTENT=2 → 抓到 DirectComposition / 分层窗口的内容
    ok = u.PrintWindow(h, mdc, 2)
    # BITMAPINFOHEADER
    class BIH(ctypes.Structure):
        _fields_ = [('biSize', ctypes.c_uint32), ('biWidth', ctypes.c_int32),
                    ('biHeight', ctypes.c_int32), ('biPlanes', ctypes.c_uint16),
                    ('biBitCount', ctypes.c_uint16), ('biCompression', ctypes.c_uint32),
                    ('biSizeImage', ctypes.c_uint32), ('biXPelsPerMeter', ctypes.c_int32),
                    ('biYPelsPerMeter', ctypes.c_int32), ('biClrUsed', ctypes.c_uint32),
                    ('biClrImportant', ctypes.c_uint32)]

    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth = w
    bi.biHeight = -hh          # top-down
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    bufsz = w * hh * 4
    buf = ctypes.create_string_buffer(bufsz)
    got = gdi.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mdc)
    u.ReleaseDC(h, hdc)
    if not got:
        return None, 0, 0
    # BGRA → QImage
    from PyQt5.QtGui import QImage
    img = QImage(buf.raw, w, hh, w * 4, QImage.Format_ARGB32)
    return img.copy(), w, hh


def main():
    target = int(sys.argv[1]) if len(sys.argv) > 1 else None
    os.makedirs(OUT, exist_ok=True)
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    if target is None:
        print('用法: winprobe89_grab.py <pid>')
        return 2

    idx = 0
    found = []

    def cb(h, _l):
        nonlocal idx
        if pid_of(h) != target:
            return True
        w0, h0 = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
        c = cls(h)
        if c == 'IME':
            return True
        img, w, hh = grab(h)
        idx += 1
        stamp = time.strftime('%H%M%S')
        if img is None or img.isNull():
            print('#%02d %-34s 抓取失败' % (idx, c))
            return True
        # ★ 放大：小窗口（38x80 宠物 / 48x48 灵魂）放大 4 倍才看得清
        scale = 4 if max(w, hh) <= 120 else (2 if max(w, hh) <= 700 else 1)
        out = img.scaled(img.width() * scale, img.height() * scale)
        fp = os.path.join(OUT, 'win_%02d_%s_%dx%d_x%d.png' % (idx, stamp, w, hh, scale))
        out.save(fp, 'PNG')
        found.append((c, w, hh, fp))
        print('#%02d %-34s %dx%d -> %s' % (idx, c, w, hh, os.path.basename(fp)))
        return True

    EnumWindows(P(cb), 0)
    print('\n共 %d 个窗口' % len(found))
    # 把三个关键窗口拼一张对照图（宠物 / 画布 / 对话框）
    return 0


if __name__ == '__main__':
    sys.exit(main())
