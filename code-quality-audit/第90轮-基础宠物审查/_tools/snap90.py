# -*- coding: utf-8 -*-
u"""第90轮：按宠物当前位置精确抓拍（走小助手 screen capture，不自己截屏）。

存在的理由：
  · `screen capture --region` 在本机**不稳定**（多次 SIGTERM），而
    `--target virtual-screen` 基本可用 ⇒ 整屏抓 + 本地裁剪。
  · 从 bash 里连着调「抓屏 + 裁剪」容易被一起 SIGTERM ⇒ 收进一个 Python 进程，
    抓屏用 subprocess 单独起（它被 SIGTERM 不影响本进程）。
用法：python snap90.py [--pad 60]
"""
import argparse
import ctypes
import ctypes.wintypes  # noqa: F401
import os
import subprocess
import sys
import time

import cv2

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

u = ctypes.windll.user32
P_CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
CLI = r'C:\Users\23002\AppData\Local\Programs\Xiaozs\ScreenAutomationHelper\ScreenAutomationHelper.exe'
D = r'C:\Users\23002\Downloads\_tmp\rec90'
PET_TITLE = 'Ralsei Pet'


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def ttl(h):
    n = u.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, b, n + 1)
    return b.value


def wins():
    out = []

    def cb(h, _l):
        if u.IsWindowVisible(h):
            out.append(h)
        return True

    u.EnumWindows(P_CB(cb), 0)
    return out


def rect(h):
    r = RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pad', type=int, default=60)
    ap.add_argument('--tag', default=None)
    args = ap.parse_args()
    os.makedirs(D, exist_ok=True)

    pet = None
    listing = []
    for h in wins():
        t = ttl(h)
        if t == PET_TITLE:
            pet = h
        listing.append((t, rect(h)))
    print('可见窗口（标题 / 矩形）：')
    for t, r in listing:
        print('   %-22r %s' % (t, r))
    if pet is None:
        print('★ 没有 Ralsei Pet 窗口')
        return 2
    l, t0, w, hh = rect(pet)
    print('宠物矩形 = (%d,%d,%d,%d)' % (l, t0, w, hh))

    tag = args.tag or time.strftime('%H%M%S')
    full = os.path.join(D, 'full_%s.png' % tag)
    p = subprocess.run([CLI, 'cli', 'screen', 'capture', '--target', 'virtual-screen',
                        '--output', full], capture_output=True, timeout=120)
    print('capture rc=%s out=%s' % (p.returncode, p.stdout.decode('utf-8', 'replace')[:120].replace('\n', ' ')))
    if not os.path.exists(full):
        print('★ 抓屏没落盘')
        return 3
    img = cv2.imread(full, cv2.IMREAD_UNCHANGED)
    H, W = img.shape[:2]
    pad = args.pad
    x0, y0 = max(0, l - pad), max(0, t0 - pad)
    x1, y1 = min(W, l + w + pad), min(H, t0 + hh + pad)
    crop = img[y0:y1, x0:x1]
    out = os.path.join(D, 'crop_%s.png' % tag)
    sc = 3 if max(crop.shape[:2]) < 400 else 1
    big = cv2.resize(crop, (crop.shape[1] * sc, crop.shape[0] * sc), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(out, big)
    print('裁剪 (%d,%d)-(%d,%d) 放大 x%d ⇒ %s' % (x0, y0, x1, y1, sc, out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
