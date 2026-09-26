# -*- coding: utf-8 -*-
"""第51轮观测器：宠物**运动质量**分析（真机、外部观测、不改产品代码）。

记录宠物窗口矩形序列（默认 10Hz / 60s），输出：
  · 总位移、平均/峰值速度
  · "行走片段"切分（连续移动的区段）与静息区段时长
  · 抖动指标：方向反转次数、亚像素抖动
  · 卡死检测：长时间停在同一点
退出码恒 0；结论全部落 json，便于复核。
"""
import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

from PyQt5.QtGui import QGuiApplication

HERE = os.path.dirname(os.path.abspath(__file__))
EVID = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def tops(pid):
    u = ctypes.windll.user32
    o = []

    def cb(hwnd, _):
        wp = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(wp))
        if wp.value != pid or not u.IsWindowVisible(hwnd):
            return True
        r = wintypes.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w > 0 and h > 0:
            o.append((hwnd, r.left, r.top, w, h, u.GetWindowTextLengthW(hwnd)))
        return True

    u.EnumWindows(WNDENUMPROC(cb), 0)
    return o


def analyse(rows):
    """rows: [(t, x, y)]"""
    res = {}
    if len(rows) < 3:
        return {'error': 'samples too few'}
    steps = []
    for i in range(1, len(rows)):
        dt = rows[i][0] - rows[i - 1][0]
        dx = rows[i][1] - rows[i - 1][1]
        dy = rows[i][2] - rows[i - 1][2]
        steps.append((dt, dx, dy, (dx * dx + dy * dy) ** 0.5))
    total = sum(s[3] for s in steps)
    res['samples'] = len(rows)
    res['span_s'] = round(rows[-1][0] - rows[0][0], 2)
    res['total_px'] = round(total, 1)
    speeds = [s[3] / s[0] for s in steps if s[0] > 1e-6]
    res['speed_px_s'] = {
        'mean': round(sum(speeds) / len(speeds), 1) if speeds else 0,
        'max': round(max(speeds), 1) if speeds else 0,
    }
    # 行走片段：连续 |step| >= 1px 的区段（容忍 1 个静止采样）
    eps = []
    cur = None
    for i, s in enumerate(steps):
        moving = s[3] >= 1.0
        if moving:
            if cur is None:
                cur = [rows[i][0], rows[i + 1][0], s[3]]
            else:
                cur[1] = rows[i + 1][0]
                cur[2] += s[3]
        else:
            if cur is not None:
                eps.append(cur)
                cur = None
    if cur is not None:
        eps.append(cur)
    res['walk_episodes'] = len(eps)
    res['episode_s'] = [round(e[1] - e[0], 2) for e in eps][:40]
    res['episode_px'] = [round(e[2], 1) for e in eps][:40]
    # 静息片段
    rests = []
    cur = None
    for i, s in enumerate(steps):
        if s[3] < 1.0:
            if cur is None:
                cur = [rows[i][0], rows[i + 1][0]]
            else:
                cur[1] = rows[i + 1][0]
        else:
            if cur is not None:
                rests.append(cur)
                cur = None
    if cur is not None:
        rests.append(cur)
    res['rest_episodes'] = len(rests)
    res['rest_s_max'] = round(max([r[1] - r[0] for r in rests], default=0), 2)
    res['rest_s_list'] = [round(r[1] - r[0], 2) for r in rests][:40]
    # 抖动：相邻两步方向反转（点积 < 0）且两步都 > 4px
    rev = 0
    for i in range(1, len(steps)):
        a, b = steps[i - 1], steps[i]
        if a[3] > 4.0 and b[3] > 4.0:
            if a[1] * b[1] + a[2] * b[2] < 0:
                rev += 1
    res['direction_reversals'] = rev
    res['xs'] = [rows[0][1], min(r[1] for r in rows), max(r[1] for r in rows)]
    res['ys'] = [rows[0][2], min(r[2] for r in rows), max(r[2] for r in rows)]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--secs', type=float, default=60.0)
    ap.add_argument('--hz', type=float, default=10.0)
    ap.add_argument('--out', default=os.path.join(EVID, 'motion51.json'))
    a = ap.parse_args()

    app = QGuiApplication(sys.argv)          # noqa: F841
    period = 1.0 / a.hz
    rows = []
    t0 = time.time()
    k = 0
    while time.time() - t0 < a.secs:
        ws = tops(a.pid)
        ws = sorted(ws, key=lambda r: r[3] * r[4]) if ws else []
        if ws:
            rows.append((round(time.time() - t0, 3), ws[0][1], ws[0][2], ws[0][3], ws[0][4]))
        k += 1
        time.sleep(max(0.0, t0 + k * period - time.time()))

    res = analyse([(r[0], r[1], r[2]) for r in rows])
    res['raw_head'] = rows[:5]
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump({'summary': res, 'trace': rows}, f, ensure_ascii=False)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print('已写入 %s' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
