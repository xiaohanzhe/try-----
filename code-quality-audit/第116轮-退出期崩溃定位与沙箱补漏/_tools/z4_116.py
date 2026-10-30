# -*- coding: utf-8 -*-
u"""z4_116.py —— 定向实验：**把画布高度钳到工作区**（不盖任务栏），看 z 序抢位是否消失。

已确立的事实链
--------------
  ① 不起桌宠：任务栏 z 名次**恒为 4**，0 次变化（`z3_116.py` 负控制）。
  ② 起桌宠：任务栏名次 **4 ↔ 312** 以 **~7 Hz** 翻（`z2_116.py`）。
  ③ 去掉每帧 `canvas.raise_()`（40 次→1 次）后**仍在翻** ⇒ 主因另有其一。
  ④ 画布是**无边框全屏窗口**（`canvas.resize(screen_w, screen_h)`，见
     `main.py` 第110轮那段）⇒ 假设：Windows 把"铺满整屏的无边框窗口"
     当成全屏应用，shell 于是反复收/放任务栏。

本实验
------
  把 `type(canvas).resize` 包一层，把高度**钳到 `availableGeometry()`**
  （= 工作区，不含任务栏），其余一切不变，再测任务栏名次翻转率。
  · 翻转 ≈ 0 ⇒ **假说成立**：全屏画布就是主因。
  · 翻转照旧 ⇒ 假说否证，回退到别处找（不许把"试过"说成"修好"）。
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
SECS = float(os.environ.get('Z4_SECS') or '4')
CLAMP = os.environ.get('Z4_CLAMP', '1') == '1'

_SB = tempfile.mkdtemp(prefix='z4_116_')
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
    sys.stdout.write('[z4_116] %s\n' % m)
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
AVAIL = scr.availableGeometry()
say('screen=%dx%d  available=%dx%d+%d+%d  ⇒ 任务栏带 = y %d..%d'
    % (scr.geometry().width(), scr.geometry().height(),
       AVAIL.width(), AVAIL.height(), AVAIL.x(), AVAIL.y(),
       AVAIL.height(), scr.geometry().height()))

CANVAS = getattr(window, 'scene_canvas', None)
_WH = int(CANVAS.winId())
_orig_resize = type(CANVAS).resize
_H_MAX = AVAIL.height()
_N = [0]


def _resize(self, w, h):
    _N[0] += 1
    if CLAMP and int(h) > _H_MAX:
        h = _H_MAX
    return _orig_resize(self, w, h)


if CLAMP:
    type(CANVAS).resize = _resize
say('CLAMP=%s  画布 resize 调用计数将记录' % CLAMP)

U32 = ctypes.windll.user32
U32.EnumWindows.restype = ctypes.c_bool
PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
U32.EnumWindows.argtypes = [PROC, ctypes.c_void_p]
U32.FindWindowW.restype = ctypes.c_void_p
U32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
U32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
TB = int(U32.FindWindowW(u'Shell_TrayWnd', None) or 0)


def order():
    out = []

    def _cb(h, lp):
        out.append(int(h))
        return True
    U32.EnumWindows(PROC(_cb), None)
    return out


Z = []


def snap():
    o = order()
    Z.append((round(time.perf_counter() - T0, 3),
              o.index(TB) if TB in o else -1,
              o.index(_WH) if _WH in o else -1))
    if Z[-1][0] >= SECS:
        tm.stop()
        _finish()


T0 = time.perf_counter()
tm = QTimer()
tm.timeout.connect(snap)
tm.start(25)
QTimer.singleShot(int((SECS + 10) * 1000), lambda: (tm.stop(), _finish()))


def _finish():
    if getattr(_finish, '_d', False):
        return
    _finish._d = True
    rep = [u'# z4_116  CLAMP=%s' % CLAMP]
    rep.append(u'任务栏带 = y %d..%d（工作区高 %d）'
               % (AVAIL.height(), scr.geometry().height(), AVAIL.height()))
    rep.append(u'画布 resize 调用 %d 次 / %.2f s' % (_N[0], Z[-1][0]))
    rep.append(u'画布最终尺寸 = %dx%d' % (CANVAS.width(), CANVAS.height()))
    v = [z[1] for z in Z]
    rep.append(u'任务栏 z 名次 取值集合 = %s' % (sorted(set(v))[:12],))
    fl = sum(1 for i in range(1, len(v)) if v[i] != v[i - 1])
    rep.append(u'任务栏名次变化 %d 次 / %.2f s ⇒ %.2f Hz'
               % (fl, Z[-1][0], fl / max(1e-9, Z[-1][0])))
    cv = [z[2] for z in Z]
    rep.append(u'画布 z 名次 取值集合 = %s' % (sorted(set(cv))[:12],))
    rep.append(u'前 10 个采样 (t, tb_z, canvas_z) = %s' % (Z[:10],))
    txt = u'\n'.join(rep) + u'\n'
    with io.open(os.path.join(OUT, 'z4_116_%s.txt'
                              % ('clamp' if CLAMP else 'noclamp')),
                 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    say(txt)
    app.quit()


rc = app.exec_()
sys.exit(rc)
