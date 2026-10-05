# -*- coding: utf-8 -*-
u"""第90轮：桌宠「站桩」取证 —— 高频采样窗口矩形，量化它到底动不动。

为什么不用小助手的 window.list-visible 高频采样：
  每次 CLI 调用要新起进程（实测 0.3~1s），拿到的是 ~1Hz，不足以判"站桩"。
  GetWindowRect 是只读查询、不改变屏幕，故这里直接用它做**测量**；
  与 App 交互的动作仍然只走小助手。

产物：stdout + C:\\Users\\23002\\Downloads\\_tmp\\rec90\\stationary.csv
"""
import ctypes
import ctypes.wintypes  # noqa: F401
import os
import sys
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

u = ctypes.windll.user32
P_CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
PET_TITLE = 'Ralsei Pet'
OUT = r'C:\Users\23002\Downloads\_tmp\rec90\stationary.csv'


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def ttl(h):
    n = u.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, b, n + 1)
    return b.value


def rect(h):
    r = RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def find():
    hits = []

    def cb(h, _l):
        if u.IsWindowVisible(h) and ttl(h) == PET_TITLE:
            hits.append(h)
        return True

    u.EnumWindows(P_CB(cb), 0)
    return hits[0] if hits else None


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    hz = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    h = find()
    if h is None:
        print('没找到 %r' % PET_TITLE)
        return 2
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    t0 = time.time()
    while time.time() - t0 < secs:
        l, t, w, hh = rect(h)
        rows.append((time.time() - t0, l, t, w, hh))
        time.sleep(1.0 / hz)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('t,x,y,w,h\n')
        for r in rows:
            fh.write('%.4f,%d,%d,%d,%d\n' % r)
    xs = [r[1] for r in rows]
    ys = [r[2] for r in rows]
    ws = [r[3] for r in rows]
    hs = [r[4] for r in rows]
    n = len(rows)
    print('采样 %.0fs @ %.0fHz ⇒ %d 个点' % (secs, hz, n))
    print('x 唯一值 %d 个，范围 [%d, %d]' % (len(set(xs)), min(xs), max(xs)))
    print('y 唯一值 %d 个，范围 [%d, %d]' % (len(set(ys)), min(ys), max(ys)))
    print('w 唯一值 %d 个 %s' % (len(set(ws)), sorted(set(ws))[:6]))
    print('h 唯一值 %d 个 %s' % (len(set(hs)), sorted(set(hs))[:6]))
    moved = sum(1 for i in range(1, n) if (xs[i], ys[i]) != (xs[i - 1], ys[i - 1]))
    print('相邻采样发生位移的次数 = %d / %d' % (moved, n - 1))
    print('[%s] 窗口在 %.0f 秒内**完全没有移动**' % ('PASS' if moved == 0 else 'FAIL', secs))
    print('CSV = %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
