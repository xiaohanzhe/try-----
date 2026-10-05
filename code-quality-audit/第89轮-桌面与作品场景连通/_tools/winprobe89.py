# -*- coding: utf-8 -*-
u"""探针：桌宠窗口的真实几何 + 可见性（第89轮「宠物不见了」排查）。

★ 必须先声明 DPI 感知，否则 GetWindowRect 会被系统按缩放比缩小。
★ 判据：窗口 rect 是否落在屏幕内 / 是否 IsWindowVisible / 是否被最小化。
"""
import ctypes
import subprocess
import sys
import os
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()
_DPI = True

u = ctypes.windll.user32
EnumWindows = u.EnumWindows
P = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def ttl(h):
    n = u.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, b, n + 1)
    return b.value


def pid_of(h):
    p = ctypes.c_ulong()
    u.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def one(h):
    r = RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return r


def main():
    target = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if target is None:
        # 起一个桌宠
        env = dict(os.environ)
        env['PYTHONIOENCODING'] = 'utf-8'
        env.pop('QT_QPA_PLATFORM', None)
        p = subprocess.Popen([sys.executable, os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')),
            'ralsei_pet', 'src', 'main.py')], cwd=os.path.abspath(os.path.join(
                os.path.dirname(__file__), '..', '..', '..', 'ralsei_pet')),
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        target = p.pid
        print('spawned pid', target)
        time.sleep(9)

    # 主屏
    print('screen =', u.GetSystemMetrics(0), u.GetSystemMetrics(1))

    def cb(h, _l):
        if pid_of(h) != target:
            return True
        r = one(h)
        vis = bool(u.IsWindowVisible(h))
        icon = bool(u.IsIconic(h))
        w, hh = r.right - r.left, r.bottom - r.top
        print('  cls=%-32s vis=%-5s iconic=%-5s rect=(%5d,%5d)-(%5d,%5d) size=%dx%d  title=%r'
              % (cls(h), vis, icon, r.left, r.top, r.right, r.bottom, w, hh, ttl(h)))
        return True

    EnumWindows(P(cb), 0)
    return 0


if __name__ == '__main__':
    sys.exit(main())
