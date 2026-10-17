# -*- coding: utf-8 -*-
u"""z2_116.py —— 列出顶层窗口真实 z 序 + 扩展样式，回答"谁在置顶"（第116轮）。

背景：`zprobe116.py` 已证明 —— 去掉每帧 `raise_()` 后，z 序**仍在翻**
（任务栏名次 313↔4，桌宠 4↔5、画布 20↔21 恒定配对）。⇒ 是**任务栏反复置顶**，
不是我们主动抢。本脚本查两件事：
  ① 我们的窗口是不是 `WS_EX_TOPMOST`（0x8）—— 若是，就能解释"平时压着任务栏"；
  ② 翻转时刻前后，z 序列表头部是谁（抓现行）。
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
OUT = os.path.join(ROUND, '_evidence', 'rec116')
os.makedirs(OUT, exist_ok=True)

_SB = tempfile.mkdtemp(prefix='z2_116_')
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
from PyQt5.QtCore import QTimer                               # noqa: E402


def say(m):
    sys.stdout.write('[z2_116] %s\n' % m)
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

U32 = ctypes.windll.user32
U32.EnumWindows.restype = ctypes.c_bool
PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
U32.EnumWindows.argtypes = [PROC, ctypes.c_void_p]
U32.FindWindowW.restype = ctypes.c_void_p
U32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
U32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
U32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
U32.GetWindowLongW.restype = ctypes.c_long
U32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
TB = int(U32.FindWindowW(u'Shell_TrayWnd', None) or 0)
CANVAS = getattr(window, 'scene_canvas', None)
OURS = {'pet': int(window.winId())}
if CANVAS is not None:
    OURS['canvas'] = int(CANVAS.winId())


def exstyle(h):
    try:
        return int(U32.GetWindowLongW(ctypes.c_void_p(h), GWL_EXSTYLE))
    except Exception:
        return -1


def cls(h):
    buf = ctypes.create_unicode_buffer(256)
    U32.GetClassNameW(ctypes.c_void_p(h), buf, 256)
    return buf.value


def title(h):
    buf = ctypes.create_unicode_buffer(256)
    U32.GetWindowTextW(ctypes.c_void_p(h), buf, 256)
    return buf.value


def order():
    out = []

    def _cb(h, lp):
        out.append(int(h))
        return True
    U32.EnumWindows(PROC(_cb), None)
    return out


rep = [u'# z2_116 —— 顶层 z 序 + 扩展样式']

for nm, h in list(OURS.items()) + [('taskbar', TB)]:
    ex = exstyle(h)
    rep.append(u'%-8s hwnd=%d class=%r exstyle=0x%08X  TOPMOST=%s '
               u'TOOLWIN=%s APPWIN=%s'
               % (nm, h, cls(h), ex,
                  bool(ex & WS_EX_TOPMOST), bool(ex & WS_EX_TOOLWINDOW),
                  bool(ex & WS_EX_APPWINDOW)))

_samples = []


def snap():
    o = order()
    pos = {}
    for nm, h in list(OURS.items()) + [('taskbar', TB)]:
        pos[nm] = o.index(h) if h in o else -1
    _samples.append((round(time.perf_counter() - T0, 3), pos, o[:8]))
    if len(_samples) >= 60:
        tm.stop()
        _finish()


T0 = time.perf_counter()
tm = QTimer()
tm.timeout.connect(snap)
tm.start(25)
QTimer.singleShot(4000, lambda: (tm.stop(), _finish()))


def _finish():
    if getattr(_finish, '_d', False):
        return
    _finish._d = True
    rep.append(u'')
    rep.append(u'采样 %d 次（%.2f s）'
               % (len(_samples), _samples[-1][0] if _samples else 0))
    rel = [1 if s[1]['pet'] < s[1]['taskbar'] else 0
           for s in _samples if s[1]['pet'] >= 0 and s[1]['taskbar'] >= 0]
    fl = sum(1 for i in range(1, len(rel)) if rel[i] != rel[i - 1])
    rep.append(u'桌宠在任务栏之上：翻转 %d 次 ⇒ %.2f Hz' % (fl, fl / 4.0))
    rep.append(u'')
    rep.append(u'前 12 个采样的 z 名次（pet/canvas/taskbar）+ 列表头 8 个窗口:')
    for t, pos, head in _samples[:12]:
        rep.append(u'  t=%.3f  %s' % (t, pos))
        rep.append(u'      head=%r'
                   % ([(cls(h), title(h)[:22],
                        bool(exstyle(h) & WS_EX_TOPMOST)) for h in head],))
    # 找一次翻转，打印其前后
    for i in range(1, len(_samples)):
        a, b = _samples[i - 1], _samples[i]
        if (a[1]['pet'] < a[1]['taskbar']) != (b[1]['pet'] < b[1]['taskbar']):
            rep.append(u'')
            rep.append(u'★ 翻转 t=%.3f：前 %s / 后 %s' % (b[0], a[1], b[1]))
            rep.append(u'   前 head=%r'
                       % ([(cls(h), title(h)[:20]) for h in a[2]],))
            rep.append(u'   后 head=%r'
                       % ([(cls(h), title(h)[:20]) for h in b[2]],))
            break
    txt = u'\n'.join(rep) + u'\n'
    with io.open(os.path.join(OUT, 'z2_116.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    say(txt)
    app.quit()


rc = app.exec_()
sys.exit(rc)
