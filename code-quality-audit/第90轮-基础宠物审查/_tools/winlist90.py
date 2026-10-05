# -*- coding: utf-8 -*-
u"""第90轮：枚举**全部**可见顶层窗口（含归属进程），定位"谁开了 Bilibili"。

为什么不用小助手的 window.list-visible：它本轮只返回 5 个窗口，
而桌面上明显还有更多（Edge 等）⇒ 对"谁开了这个窗口"的取证不够用。
本脚本只读枚举 + psutil 查进程名，不改变任何状态。
"""
import ctypes
import ctypes.wintypes  # noqa: F401
import sys

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import psutil

u = ctypes.windll.user32
P_CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def ttl(h):
    n = u.GetWindowTextLengthW(h)
    if n <= 0:
        return ''
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, b, n + 1)
    return b.value


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def wpid(h):
    p = ctypes.c_ulong()
    u.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def rect(h):
    r = RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def pname(pid):
    try:
        return psutil.Process(pid).name()
    except Exception:
        return '?'


def main():
    pet_pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = []

    def cb(h, _l):
        if not u.IsWindowVisible(h):
            return True
        t = ttl(h)
        l, tp, w, hh = rect(h)
        if w <= 0 or hh <= 0:
            return True
        rows.append((wpid(h), t, cls(h), (l, tp, w, hh)))
        return True

    u.EnumWindows(P_CB(cb), 0)
    rows.sort(key=lambda r: (-(r[3][2] * r[3][3])))
    print('共 %d 个可见顶层窗口（按面积降序）' % len(rows))
    print('%-8s %-24s %-28s %-22s %s' % ('pid', 'process', 'class', 'rect(l,t,w,h)', 'title'))
    print('-' * 118)
    for pid, t, c, r in rows:
        mark = ' ★宠物' if pet_pid and pid == pet_pid else ''
        print('%-8d %-24s %-28s %-22s %s%s' % (pid, pname(pid)[:24], c[:28],
                                               '%d,%d,%d,%d' % r, (t or '-')[:40], mark))
    print()
    if pet_pid:
        kids = [p for p in psutil.process_iter(['pid', 'name'])
                if p.info['pid'] != pet_pid]
        # 宠物直接/间接子进程
        out = []
        try:
            me = psutil.Process(pet_pid)
            for ch in me.children(recursive=True):
                out.append((ch.pid, ch.name()))
        except Exception as e:
            print('取子进程失败', e)
        print('宠物(pid=%d)的子进程：%s' % (pet_pid, out if out else '（无）'))
    # 找 bilibili 相关
    print()
    print('含 bil/bilibili/哔哩 的窗口：')
    hit = False
    for pid, t, c, r in rows:
        if any(k in t.lower() for k in ('bil', '哔哩', 'bilibili')):
            print('   pid=%d %s %s %s' % (pid, pname(pid), r, t))
            hit = True
    if not hit:
        print('   （无）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
