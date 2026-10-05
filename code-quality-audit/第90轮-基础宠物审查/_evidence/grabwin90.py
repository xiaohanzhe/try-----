# -*- coding: utf-8 -*-
u"""第90轮 · 逐窗口 PrintWindow 抓图（第89轮血泪：grabWindow(0) 抓不到分层窗口）

用法: python grabwin90.py <pid>
产物: 第90轮-基础宠物审查/_evidence/shots/win_NN_*.png
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
P = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

HERE = os.path.abspath(os.path.dirname(__file__))
OUT = os.path.join(HERE, 'shots')


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


def rect_of(h):
    r = RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def grab(h):
    l, t, w, hh = rect_of(h)
    if w <= 0 or hh <= 0:
        return None
    hdc = u.GetWindowDC(h)
    mdc = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, w, hh)
    gdi.SelectObject(mdc, bmp)
    u.PrintWindow(h, mdc, 2)          # PW_RENDERFULLCONTENT

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
    bi.biHeight = -hh
    bi.biPlanes = 1
    bi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * hh * 4)
    got = gdi.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mdc)
    u.ReleaseDC(h, hdc)
    if not got:
        return None
    from PyQt5.QtGui import QImage
    img = QImage(buf.raw, w, hh, w * 4, QImage.Format_ARGB32)
    return img.copy()


def main():
    if len(sys.argv) < 2:
        print('用法: grabwin90.py <pid>')
        return 2
    target = int(sys.argv[1])
    os.makedirs(OUT, exist_ok=True)
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    rows = []

    def cb(h, _l):
        if pid_of(h) != target or not u.IsWindowVisible(h):
            return True
        c = cls(h)
        if c == 'IME':
            return True
        l, t, w, hh = rect_of(h)
        img = grab(h)
        idx = len(rows) + 1
        tag = '%02d_%s_%dx%d' % (idx, c.replace('Qt5152QWindow', 'Q'), w, hh)
        fp = os.path.join(OUT, 'win_%s.png' % tag)
        saved = '-'
        if img is not None and not img.isNull():
            sc = 4 if max(w, hh) <= 120 else (2 if max(w, hh) <= 700 else 1)
            img.scaled(img.width() * sc, img.height() * sc).save(fp, 'PNG')
            saved = os.path.basename(fp)
        rows.append((idx, c, l, t, w, hh, ttl(h), saved))
        return True

    u.EnumWindows(P(cb), 0)
    print('%-4s %-32s %-22s %-16s %s' % ('#', 'class', 'rect(l,t,w,h)', 'title', 'shot'))
    print('-' * 110)
    for idx, c, l, t, w, hh, ti, saved in rows:
        print('%-4d %-32s (%d,%d,%d,%d)%-6s %-16s %s'
              % (idx, c, l, t, w, hh, '', (ti or '-')[:15], saved))
    print()
    print('共 %d 个可见窗口' % len(rows))
    sizes = [(w, hh) for _i, _c, _l, _t, w, hh, _ti, _s in rows]
    has_canvas = any(w >= 600 and hh >= 400 for w, hh in sizes)
    print('★ 存在 >=600x400 的画布窗口: %s' % has_canvas)
    return 0


if __name__ == '__main__':
    sys.exit(main())
