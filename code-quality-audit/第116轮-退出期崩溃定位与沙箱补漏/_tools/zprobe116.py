# -*- coding: utf-8 -*-
u"""zprobe116.py —— **点名**是谁在周期性抢顶层窗口（第116轮「对话框/门在闪现」）。

已确证的事实（同轮 `band116.py` 实测）
--------------------------------------
· 屏下沿 y≈1528..1600（Windows 任务栏那一条）以 **~4.2 Hz** 在
  「我们的对话框」↔「任务栏」之间来回翻（`band116_b6_stateHi/Lo.png` 两图直给）。
· 也就是**桌宠窗口与任务栏的 z 序在抖**，而不是"门在闪"或"框在闪"。

本脚本回答"谁在抖"
------------------
给下列方法挂**只计数、不改行为**的包装（透明记录器）：
  · 桌宠窗口：`show` / `raise_` / `activateWindow` / `setWindowFlags` / `move`
  · 对话窗口：同上
  · 场景画布：`show` / `raise_` / `setWindowFlags`
  · 桌宠窗口 `event()` 里收到的 `WindowActivate` / `Show` 事件
再以 30 Hz 采 `EnumWindows` 里"画布 / 桌宠 / 任务栏"三者的名次，
把"翻 z 序的时刻"与"谁刚被调用"对齐。
"""
import ctypes
import io
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
PKG = os.path.abspath(os.path.join(ROUND, '..', '..', 'ralsei_pet'))
SRC = os.path.join(PKG, 'src')
OUT = os.environ.get('PROBE_OUT', os.path.join(ROUND, '_evidence', 'rec116'))
os.makedirs(OUT, exist_ok=True)
SECS = float(os.environ.get('ZP_SECS') or '4')

_SB = tempfile.mkdtemp(prefix='zp116_')
for _s in ('vault', 'staging', 'desktop'):
    os.makedirs(os.path.join(_SB, _s), exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(_SB, 'vault')
os.environ['RALSEI_DATA_DIR'] = os.path.join(_SB, 'staging')
os.environ['RALSEI_DESKTOP'] = os.path.join(_SB, 'desktop')
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')
os.chdir(PKG)
sys.path.insert(0, SRC)

import main as M                                              # noqa: E402
from PyQt5.QtWidgets import QApplication                      # noqa: E402
from PyQt5.QtCore import QTimer, QEvent                       # noqa: E402


def say(m):
    sys.stdout.write('[zp116] %s\n' % m)
    sys.stdout.flush()


M.check_single_instance()
M.install_crash_guard()
try:
    import data_store
    data_store.vault_root = lambda create=True: None
    data_store.migrate_from_staging()
except Exception:
    pass

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass
scr = app.primaryScreen()
_W, _H = scr.geometry().width(), scr.geometry().height()

# ---- Win32 ----
U32 = ctypes.windll.user32
U32.EnumWindows.restype = ctypes.c_bool
PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
U32.EnumWindows.argtypes = [PROC, ctypes.c_void_p]
U32.FindWindowW.restype = ctypes.c_void_p
U32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
U32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
TB = int(U32.FindWindowW(u'Shell_TrayWnd', None) or 0)

CANVAS = getattr(window, 'scene_canvas', None)
DLG = getattr(window, 'dialogue_ui', None)
TARGETS = [('pet', window)]
if CANVAS is not None:
    TARGETS.append(('canvas', CANVAS))
if DLG is not None:
    TARGETS.append(('dlg', DLG))

LOG = []          # (t, name, meth)
_T0 = time.perf_counter()
_METHS = ('show', 'raise_', 'activateWindow', 'setWindowFlags',
          'lower', 'setWindowOpacity', 'setAttribute')


def _wrap(name, obj):
    for m in _METHS:
        fn = getattr(obj, m, None)
        if fn is None or not callable(fn):
            continue

        def _mk(fn, m, name):
            def _f(*a, **kw):
                LOG.append((round(time.perf_counter() - _T0, 3), name, m))
                return fn(*a, **kw)
            return _f
        try:
            setattr(obj, m, _mk(fn, m, name))
        except Exception:
            pass


for nm, ob in TARGETS:
    _wrap(nm, ob)

_WH = {nm: int(ob.winId()) for nm, ob in TARGETS}
say('pid=%d screen=%dx%d 观测对象=%r 任务栏 hwnd=%d'
    % (os.getpid(), _W, _H, [n for n, _ in TARGETS], TB))


def _zorder():
    out = []

    def _cb(h, lp):
        out.append(int(h))
        return True
    try:
        U32.EnumWindows(PROC(_cb), None)
    except Exception:
        return {}
    d = {}
    for nm, h in list(_WH.items()) + [('taskbar', TB)]:
        try:
            d[nm] = out.index(h)
        except ValueError:
            d[nm] = -1
    return d


Z = []
_act = []


def evfilter(o, e):
    try:
        t = e.type()
        if t in (QEvent.WindowActivate, QEvent.Show, QEvent.WindowStateChange):
            _act.append((round(time.perf_counter() - _T0, 3),
                         'pet-event-%d' % int(t)))
    except Exception:
        pass
    return _orig_ev(o, e)


_orig_ev = type(window).event
type(window).event = evfilter


def tick():
    t = round(time.perf_counter() - _T0, 3)
    z = _zorder()
    Z.append((t, z.get('pet', -1), z.get('canvas', -1),
              z.get('taskbar', -1)))
    if t >= SECS:
        tm.stop()
        _finish()


tm = QTimer()
tm.timeout.connect(tick)
tm.start(33)
QTimer.singleShot(int((SECS + 10) * 1000), lambda: (tm.stop(), _finish()))


def _finish():
    if getattr(_finish, '_d', False):
        return
    _finish._d = True
    rep = [u'# zprobe116 观察 %.1fs' % SECS]
    rep.append(u'调用计数（%.1fs 内）:' % SECS)
    from collections import Counter
    c = Counter((n, m) for _t, n, m in LOG)
    for k in sorted(c):
        rep.append(u'   %-8s %-18s %d 次' % (k[0], k[1], c[k]))
    if not LOG:
        rep.append(u'   （一次都没有）')
    rep.append(u'')
    rep.append(u'桌宠事件: %d 次' % len(_act))
    for a in _act[:20]:
        rep.append(u'   %s' % (a,))
    rep.append(u'')
    if Z:
        vs = [z[1] for z in Z]
        tsb = [z[3] for z in Z]
        rep.append(u'桌宠窗口 z 名次 取值集合 = %s'
                   % (sorted(set(vs))[:10],))
        rep.append(u'任务栏 z 名次 取值集合 = %s'
                   % (sorted(set(tsb))[:10],))
        rel = [1 if z[1] < z[3] and z[1] >= 0 else 0 for z in Z]
        fl = sum(1 for i in range(1, len(rel)) if rel[i] != rel[i - 1])
        rep.append(u'桌宠在任务栏之上：翻转 %d 次 / %d 采样（%.1f s）'
                   u'⇒ %.2f Hz'
                   % (fl, len(Z), Z[-1][0], fl / max(1e-9, Z[-1][0])))
        rep.append(u'最早 12 个采样 (t, pet, canvas, taskbar) = %s'
                   % (Z[:12],))
        rep.append(u'最后一次翻转附近 z = %s'
                   % (Z[max(0, len(Z) // 2 - 3):len(Z) // 2 + 3],))
    rep.append(u'')
    rep.append(u'与 z 采样对齐的近 40 条调用:')
    for e in LOG[:40]:
        rep.append(u'   %s' % (e,))
    txt = u'\n'.join(rep) + u'\n'
    with io.open(os.path.join(OUT, 'zprobe116.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    say(txt)
    app.quit()


rc = app.exec_()
sys.exit(rc)
