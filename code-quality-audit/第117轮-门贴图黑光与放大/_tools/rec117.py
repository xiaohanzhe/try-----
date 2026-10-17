# -*- coding: utf-8 -*-
u"""rec117.py —— 桌面四门「**真机录屏 + 逐帧取证**」（用户 10-18：「可以录屏逐帧检查了」）。

为什么要录屏，而不是再抓几张静态图
----------------------------------
第117轮前面已经抓过**静态**四门裁图（`shot117_doorform.py`）+ 逐像素对账。
但静态图只能回答"**某一刻**对不对"，回答不了"**一直**对不对"：

  · 四门放大后（`DOOR_FIT_CAP` 1.2→1.6）会不会**在某几帧抖动/漂移**？
  · 门 A 的黑光会不会**闪回**品红（`door_reveal` 的渐显动画在跑）？
  · 第116轮修掉的**对话框闪现 / 任务栏翻转**有没有被本轮放大**带回来**？
  · 门 B 贴在底边，**对话框常驻**会不会整块盖住它？

⇒ 本脚本录 ~14 s，每帧同时落三份**互相独立**的证据：
  ① **画面**（`rec117.avi`，可人眼看）；
  ② **产品状态**（四门 sprite/rect/alpha、对话框 opacity/vis/rect、任务栏 z 名次、
     桌宠 `frameGeometry()`）—— **内省值**；
  ③ **该帧四门「贴图不透明区」的像素统计**（`mean_lum` / `mean RGB` / 近黑占比 / CRC）
     —— **像素值**，且**只在 alpha≥250 的贴图内部取**（不是整矩形平均！
     整矩形会把壁纸算进来，第117轮第一版就这么把门 A 的 19.8 量成 65.1）。

★★★ 两个「不保真」教训（第一版录屏踩到，已修）
---------------------------------------------
1. **画布尺寸必须取 `window._desktop_layer_size()`**（= 工作区 2560×**1528**），
   不能取 `primaryScreen().geometry()`（= 整屏 1600）。
   产品调用点是 `canvas.set_screen_doors(self._desktop_screen_doors(int(sw), int(sh)))`。
   取错 72 px ⇒ 门 B/C/D 的 y 整体偏 72 px（B 被推到任务栏里）⇒ **报的是假问题**。
2. **帧率如实记，不谎称"逐帧"**：全屏 `grabWindow` + mp4v 编码在 2560×1600 上
   只有 **~3 Hz**（本文件末尾会打印实测）。3 Hz **判不了 5~7 Hz 的闪烁**（会混叠）
   ⇒ 闪烁另有高速探针 `fast117.py`（40 Hz，只抓门的小矩形）。
   本脚本只负责"看录像 + 稳态/颜色/几何/遮挡"。

相位
----
  P1（0~`REC117_HIDE_AT`，默认 7.0 s）**原样**：对话框在场 ⇒ 量"门被遮多少"（真实观感）。
  P2（之后）`dialogue_ui.hide()` ⇒ 量"门本体现在对不对"。
  ★ hide 只改**可见性**，不改任何几何 ⇒ 门 alpha / rect 不受影响（与 `shot117` 同理由）。

★ 沙箱：`RALSEI_MEMORY_DIR` / `RALSEI_DATA_DIR` / `RALSEI_DESKTOP` 三把闸，
  且**必须设在 `import main` 之前**（顺序反了等于没设，第116轮实证）。
  跑完用 `_shared/vault_guard.py diff` 独立复核用户记忆库。

跑法
----
  set REC117_SECS=14
  C:\\Python311\\python.exe code-quality-audit\\第117轮-门贴图黑光与放大\\_tools\\rec117.py
逐帧判据见 `check117_rec.py`（**独立重读 avi + csv**，不信本脚本的实时统计）。
"""
import csv
import ctypes
import io
import os
import sys
import tempfile
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
ASSETS = os.path.join(PKG, 'assets', 'scenes')
OUT = os.environ.get('REC117_OUT', os.path.join(ROUND, '_evidence', 'rec117'))
SECS = float(os.environ.get('REC117_SECS') or '14')
TICK_MS = int(os.environ.get('REC117_TICK_MS') or '100')
T_HIDE = float(os.environ.get('REC117_HIDE_AT') or '7.0')
os.makedirs(OUT, exist_ok=True)

# ---- 沙箱三闸（必须在 import main 之前）----
_SB = tempfile.mkdtemp(prefix='rec117_')
for _s in ('vault', 'staging', 'desktop'):
    os.makedirs(os.path.join(_SB, _s), exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(_SB, 'vault')
os.environ['RALSEI_DATA_DIR'] = os.path.join(_SB, 'staging')
os.environ['RALSEI_DESKTOP'] = os.path.join(_SB, 'desktop')
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import cv2                                                       # noqa: E402
import numpy as np                                               # noqa: E402
from PIL import Image                                            # noqa: E402
import main as M                                                 # noqa: E402
from PyQt5.QtWidgets import QApplication                         # noqa: E402
from PyQt5.QtCore import QTimer                                  # noqa: E402


def say(m):
    sys.stdout.write('[rec117] %s\n' % m)
    sys.stdout.flush()


say('沙箱 = %s' % _SB)
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
_scr = app.primaryScreen()
_SCR_W, _SCR_H = _scr.geometry().width(), _scr.geometry().height()
# ★★★ 画布尺寸（= 工作区，扣掉任务栏）。必须用产品自己的函数，不能拿整屏。
_W, _H = window._desktop_layer_size()
_W, _H = int(_W), int(_H)
say('shown pid=%d 整屏=%dx%d 画布=%dx%d' % (os.getpid(), _SCR_W, _SCR_H, _W, _H))
if (_SCR_W, _SCR_H) == (_W, _H):
    say('!! 警告：画布 == 整屏（任务栏没扣掉？）—— 门 B 会落到任务栏里')

# ---- Win32：任务栏 z 名次（第116轮固定走法：EnumWindows）----
_U32 = ctypes.windll.user32
_U32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                               ctypes.c_void_p), ctypes.c_void_p]
_U32.EnumWindows.restype = ctypes.c_bool
_U32.FindWindowW.restype = ctypes.c_void_p
_U32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]


def _top_windows():
    out = []

    def _cb(h, _lp):
        out.append(int(h))
        return True

    try:
        _U32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                            ctypes.c_void_p)(_cb), None)
    except Exception:
        pass
    return out


_TASKBAR = int(_U32.FindWindowW(u'Shell_TrayWnd', None) or 0)


def _taskbar_z():
    if not _TASKBAR:
        return None
    for i, h in enumerate(_top_windows()):
        if h == _TASKBAR:
            return i
    return None


d = getattr(window, 'dialogue_ui', None)
say('dialogue_ui = %r' % (type(d).__name__ if d is not None else None))

_LETTER_OF = {
    'objs/desk_door_oneshot_black.png': 'A',
    'objs/niko_door_portal.png': 'B',
    'objs/desk_door_ut.png': 'C',
    'objs/desk_door_deltarune.png': 'D',
}
_MASK = {}


def _mask_of(sid, w, h):
    u"""贴图 alpha≥250 的**内部**掩膜（NEAREST 缩放到矩形尺寸）⇒ bool 数组。

    ★ 必须用 NEAREST：产品落笔是 `drawPixmap`（最近邻），用 LANCZOS 会把
      细线门的边缘和背景混在一起（第117轮 `verify117_shot` 首版假红 12.78 的真因）。
    """
    key = (sid, w, h)
    if key in _MASK:
        return _MASK[key]
    p = os.path.join(ASSETS, sid.replace('/', os.sep))
    try:
        im = Image.open(p).convert('RGBA')
        if im.size != (w, h):
            im = im.resize((w, h), Image.NEAREST)
        a = np.array(im)[:, :, 3]
        m = a >= 250
        if m.shape[0] >= 3 and m.shape[1] >= 3:
            # 再腐蚀 1 px：只比"内部实心像素"（边缘会被背景混色）
            e = m.copy()
            e[1:-1, 1:-1] = (m[1:-1, 1:-1] & m[:-2, 1:-1] & m[2:, 1:-1]
                             & m[1:-1, :-2] & m[1:-1, 2:])
            e[0, :] = e[-1, :] = False
            e[:, 0] = e[:, -1] = False
            m = e
        _MASK[key] = m
        return m
    except Exception as ex:                                      # noqa: BLE001
        say('掩膜失败 %s: %r' % (sid, ex))
        return None


def _doors_now():
    try:
        return list(window._desktop_screen_doors(_W, _H) or [])
    except Exception as e:                                       # noqa: BLE001
        say('_desktop_screen_doors 异常 %r' % (e,))
        return []


def _door_stats(arr, rect, sid):
    u"""只在贴图不透明区内统计 ⇒ (mean_lum, r, g, b, frac_black, crc, n)。"""
    x, y, w, h = [int(v) for v in rect]
    hh, ww = arr.shape[0], arr.shape[1]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(ww, x + w), min(hh, y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    sub = arr[y0:y1, x0:x1]
    m = _mask_of(sid, w, h)
    if m is not None and m.shape == sub.shape[:2] and m.any():
        px = sub[m]
    else:
        px = sub.reshape(-1, 3)
    lum = px.astype(np.float32).mean(axis=1)
    return (float(lum.mean()), float(px[:, 0].mean()), float(px[:, 1].mean()),
            float(px[:, 2].mean()), float((px.max(axis=1) < 16).mean()),
            int(zlib.crc32(px.tobytes()) & 0xffffffff), int(px.shape[0]))


RAW = os.path.join(OUT, 'rec117.avi')
_vw = cv2.VideoWriter(RAW, cv2.VideoWriter_fourcc(*'mp4v'),
                      max(1.0, 1000.0 / TICK_MS), (_SCR_W, _SCR_H))
if not _vw.isOpened():
    say('FATAL VideoWriter 打不开（目录不可写？）')
    sys.exit(2)

_csv = io.open(os.path.join(OUT, 'rec117_frames.csv'), 'w',
               encoding='utf-8', newline='')
_cw = csv.writer(_csv, lineterminator='\n')
COLS = ['i', 't', 'phase', 'tw']
for L in 'ABCD':
    COLS += ['%s_alpha' % L, '%s_x' % L, '%s_y' % L, '%s_w' % L, '%s_h' % L,
             '%s_lum' % L, '%s_r' % L, '%s_g' % L, '%s_b' % L,
             '%s_black' % L, '%s_crc' % L, '%s_n' % L]
COLS += ['dlg_op', 'dlg_vis', 'dlg_x', 'dlg_y', 'dlg_w', 'dlg_h',
         'tb_z', 'pet_x', 'pet_y', 'pet_w', 'pet_h', 'pet_vis', 't_grab', 't_enc']
_cw.writerow(COLS)

_N = [0]
_t0 = time.time()
_hid = [False]
_TG = [0.0, 0]
_TE = [0.0, 0]
_KEYDIR = os.path.join(OUT, 'keyframes')
os.makedirs(_KEYDIR, exist_ok=True)


def tick():
    i = _N[0]
    el = time.time() - _t0
    phase = 'P2' if _hid[0] else 'P1'
    g0 = time.time()
    pm = _scr.grabWindow(0)
    img = pm.toImage()
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    arr = np.frombuffer(bytes(ptr), np.uint8).reshape(
        img.height(), img.bytesPerLine() // 4, 4)
    arr = np.ascontiguousarray(arr[:, :img.width(), :3])
    _TG[0] += time.time() - g0
    _TG[1] += 1
    e0 = time.time()
    _vw.write(arr)
    _TE[0] += time.time() - e0
    _TE[1] += 1

    row = {'i': i, 't': '%.3f' % el, 'phase': phase,
           'tw': '%.4f' % time.perf_counter(),
           't_grab': '%.3f' % (time.time() - g0)}
    for it in _doors_now():
        try:
            sid, r, a = str(it[0]), tuple(it[1]), float(it[2])
        except Exception:
            continue
        L = _LETTER_OF.get(sid)
        if not L:
            continue
        st = _door_stats(arr, r, sid)
        row['%s_alpha' % L] = '%.4f' % a
        row['%s_x' % L], row['%s_y' % L] = r[0], r[1]
        row['%s_w' % L], row['%s_h' % L] = r[2], r[3]
        if st:
            row['%s_lum' % L] = '%.3f' % st[0]
            row['%s_r' % L] = '%.2f' % st[1]
            row['%s_g' % L] = '%.2f' % st[2]
            row['%s_b' % L] = '%.2f' % st[3]
            row['%s_black' % L] = '%.4f' % st[4]
            row['%s_crc' % L] = st[5]
            row['%s_n' % L] = st[6]

    if d is not None:
        row['dlg_op'] = '%.3f' % float(d.windowOpacity())
        row['dlg_vis'] = int(bool(d.isVisible()))
        g = d.geometry()
        row['dlg_x'], row['dlg_y'] = g.x(), g.y()
        row['dlg_w'], row['dlg_h'] = g.width(), g.height()
    z = _taskbar_z()
    row['tb_z'] = '' if z is None else z
    fg = window.frameGeometry()
    row['pet_x'], row['pet_y'] = fg.x(), fg.y()
    row['pet_w'], row['pet_h'] = fg.width(), fg.height()
    row['pet_vis'] = int(bool(window.isVisible()))
    _cw.writerow([row.get(c, '') for c in COLS])

    if (not _hid[0]) and el >= T_HIDE and d is not None:
        try:
            d.hide()
            app.processEvents()
            _hid[0] = True
            say('t=%.2f 已 hide 对话框 ⇒ 进入 P2' % el)
        except Exception as e:                                   # noqa: BLE001
            say('hide 失败 %r' % (e,))

    if i % max(1, int(2000.0 / TICK_MS)) == 0:
        pm.save(os.path.join(_KEYDIR, 'k%03d_t%05.1f.png' % (i, el)))

    _N[0] += 1
    if el >= SECS:
        _csv.flush()
        _csv.close()
        _vw.release()
        el2 = time.time() - _t0
        say('录完 %d 帧 / %.2f s ⇒ **实测 %.2f Hz**' % (_N[0], el2, _N[0] / el2))
        say('  平均 grab %.0f ms / encode %.0f ms ⇒ 上限约 %.1f Hz'
            % (1000 * _TG[0] / max(1, _TG[1]), 1000 * _TE[0] / max(1, _TE[1]),
               1000.0 / max(1e-6, 1000 * (_TG[0] + _TE[0]) / max(1, _TG[1]))))
        say('avi = %s (%.1f MB)' % (RAW, os.path.getsize(RAW) / 1048576.0))
        if d is not None and _hid[0]:
            try:
                d.show()
                app.processEvents()
            except Exception:
                pass
        app.quit()


_tm = QTimer()
_tm.timeout.connect(tick)
_tm.start(TICK_MS)
app.exec_()
say('done')
