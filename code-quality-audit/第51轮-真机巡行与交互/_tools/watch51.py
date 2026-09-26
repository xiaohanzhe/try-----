# -*- coding: utf-8 -*-
"""第51轮观测器：连续采样宠物窗口的**真实屏幕矩形**，回答"到底动没动"。

用法：
    python watch51.py --pid 10756 --secs 12 --hz 4 [--shots 出图目录]

不做任何猜测：每 N 毫秒枚举一次该 pid 的可见顶层窗口，记录主窗口矩形，
最后给出：位移总量 / 速度 / 抖动（相邻帧反向） / 每帧截图拼图。
"""
import argparse
import ctypes
import os
import sys
import time
from ctypes import wintypes

from PyQt5.QtGui import QGuiApplication

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def tops(pid):
    user32 = ctypes.windll.user32
    out = []

    def cb(hwnd, _):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w > 0 and h > 0:
            out.append((hwnd, r.left, r.top, w, h))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--secs', type=float, default=10.0)
    ap.add_argument('--hz', type=float, default=4.0)
    ap.add_argument('--shots', default='')
    ap.add_argument('--tag', default='pet')
    ap.add_argument('--pick', default='small',
                    help='small=最小窗口(宠物本体)  big=最大窗口')
    a = ap.parse_args()

    app = QGuiApplication(sys.argv)          # noqa: F841
    scr = QGuiApplication.primaryScreen()
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)

    period = 1.0 / max(0.5, a.hz)
    rows = []
    t0 = time.time()
    k = 0
    while time.time() - t0 < a.secs:
        ts = time.time() - t0
        ws = tops(a.pid)
        if not ws:
            rows.append((round(ts, 2), None))
        else:
            ws_sorted = sorted(ws, key=lambda r: r[3] * r[4])
            w = ws_sorted[0] if a.pick == 'small' else ws_sorted[-1]
            rows.append((round(ts, 2), w))
            if a.shots and k % 2 == 0:
                pad = 30
                x, y = w[1] - pad, w[2] - pad
                pm = scr.grabWindow(0, x, y, w[3] + pad * 2, w[4] + pad * 2)
                pm.save(os.path.join(a.shots, '%s_%02d_%s.png'
                                     % (a.tag, k, int(ts * 10))), 'PNG')
        k += 1
        time.sleep(max(0.0, t0 + k * period - time.time()))

    print('样本 %d 个（%.1fs @ %.1fHz）' % (len(rows), a.secs, a.hz))
    prev = None
    total = 0.0
    rev = 0
    for ts, w in rows:
        if w is None:
            print('  %6.2fs  无可见窗口' % ts)
            continue
        cx, cy = w[1] + w[3] / 2.0, w[2] + w[4] / 2.0
        d = ''
        if prev is not None:
            dx, dy = cx - prev[0], cy - prev[1]
            dist = (dx * dx + dy * dy) ** 0.5
            total += dist
            d = '  Δ=(%+7.1f,%+7.1f) |Δ|=%6.2f' % (dx, dy, dist)
        print('  %6.2fs  rect=(%5d,%5d,%4d,%4d)  中心=(%7.1f,%7.1f)%s'
              % (ts, w[1], w[2], w[3], w[4], cx, cy, d))
        prev = (cx, cy)
    print('--- 累计位移 %.2f px / %.1fs = %.2f px/s ---'
          % (total, a.secs, total / max(1e-6, a.secs)))
    if a.shots:
        print('截图目录：%s' % a.shots)
    return 0


if __name__ == '__main__':
    sys.exit(main())
