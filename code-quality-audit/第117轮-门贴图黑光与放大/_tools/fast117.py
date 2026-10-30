# -*- coding: utf-8 -*-
u"""fast117.py —— **40 Hz 高速探针**：专门量「门在闪吗」（`rec117.py` 只有 ~3 Hz）。

为什么必须另起一个脚本
----------------------
`rec117.py` 录全屏 avi，在 2560×1600 上「`grabWindow` 全屏 + mp4v 编码」实测只有
**~3 Hz**。3 Hz 采 5~7 Hz 的闪烁会**混叠**（第116轮 `band116.py` 就是为这个才存在：
8.2 Hz 时"光标闪"和"整框跳"分不开）。

本脚本换个取法：**只抓每个门自己的小矩形**（194×129 / 45×100 / 182×157），
单次 `grabWindow(0, x, y, w, h)` 只要几毫秒 ⇒ 40 Hz（25 ms）跑得动，
Nyquist 20 Hz > 7 Hz ⇒ **不会混叠**。

每个样本落
----------
  · 每扇门：`alpha`（内省）+ 掩膜内 `mean_lum` / `crc`（像素）⇒ **两个口径各自独立**。
  · 对话框：`opacity` / `visible` / `geometry`（内省）
  · 任务栏 z 名次（Win32 `EnumWindows`）
  · 该样本的真实时间戳（用于算实测 Hz 与抖动周期）

★ 判据在 `check117_rec.py`（独立读 CSV 复算），本脚本只负责**采得准、采得快**。
★ 沙箱三闸设在 `import main` 之前；跑完用 `vault_guard.py diff` 复核。

跑法
----
  set FAST117_SECS=8
  C:\\Python311\\python.exe code-quality-audit\\第117轮-门贴图黑光与放大\\_tools\\fast117.py
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
SECS = float(os.environ.get('FAST117_SECS') or '8')
TICK_MS = int(os.environ.get('FAST117_TICK_MS') or '25')
os.makedirs(OUT, exist_ok=True)

_SB = tempfile.mkdtemp(prefix='fast117_')
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

import numpy as np                                               # noqa: E402
from PIL import Image                                            # noqa: E402
import main as M                                                 # noqa: E402
from PyQt5.QtWidgets import QApplication                         # noqa: E402
from PyQt5.QtCore import QTimer                                  # noqa: E402


def say(m):
    sys.stdout.write('[fast117] %s\n' % m)
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
_W, _H = [int(v) for v in window._desktop_layer_size()]
say('画布 = %dx%d' % (_W, _H))

_U32 = ctypes.windll.user32
_U32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                               ctypes.c_void_p), ctypes.c_void_p]
_U32.FindWindowW.restype = ctypes.c_void_p
_U32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]


def _taskbar_z():
    tb = int(_U32.FindWindowW(u'Shell_TrayWnd', None) or 0)
    if not tb:
        return None
    out = []

    def _cb(h, _lp):
        out.append(int(h))
        return True

    try:
        _U32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                            ctypes.c_void_p)(_cb), None)
    except Exception:
        return None
    return out.index(tb) if tb in out else None


d = getattr(window, 'dialogue_ui', None)
_LETTER_OF = {
    'objs/desk_door_oneshot_black.png': 'A',
    'objs/niko_door_portal.png': 'B',
    'objs/desk_door_ut.png': 'C',
    'objs/desk_door_deltarune.png': 'D',
}
_MASK = {}


def _mask_of(sid, w, h):
    key = (sid, w, h)
    if key in _MASK:
        return _MASK[key]
    try:
        im = Image.open(os.path.join(ASSETS, sid.replace('/', os.sep))).convert('RGBA')
        if im.size != (w, h):
            im = im.resize((w, h), Image.NEAREST)
        a = np.array(im)[:, :, 3]
        m = a >= 250
        if m.shape[0] >= 3 and m.shape[1] >= 3:
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


def _grab_region(x, y, w, h):
    pm = _scr.grabWindow(0, int(x), int(y), int(w), int(h))
    img = pm.toImage()
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    a = np.frombuffer(bytes(ptr), np.uint8).reshape(
        img.height(), img.bytesPerLine() // 4, 4)
    return np.ascontiguousarray(a[:, :img.width(), :3])


def _grab_full():
    pm = _scr.grabWindow(0)
    img = pm.toImage()
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    a = np.frombuffer(bytes(ptr), np.uint8).reshape(
        img.height(), img.bytesPerLine() // 4, 4)
    return np.ascontiguousarray(a[:, :img.width(), :3])


def _stat(sub, sid, w, h):
    m = _mask_of(sid, w, h)
    px = sub[m] if (m is not None and m.shape == sub.shape[:2] and m.any()) else sub.reshape(-1, 3)
    lum = px.astype(np.float32).mean(axis=1)
    return (float(lum.mean()), int(zlib.crc32(px.tobytes()) & 0xffffffff), int(px.shape[0]))


COLS = ['i', 't', 'dt']
for L in 'ABCD':
    COLS += ['%s_alpha' % L, '%s_lum' % L, '%s_crc' % L]
COLS += ['dlg_op', 'dlg_vis', 'dlg_y', 'dlg_h', 'tb_z']
_csv = io.open(os.path.join(OUT, 'fast117_samples.csv'), 'w',
               encoding='utf-8', newline='')
_cw = csv.writer(_csv, lineterminator='\n')
_cw.writerow(COLS)

# ★★★ 第117轮：不满足于"采样"，直接把**写入路径**插桩。
#   `_desktop_screen_doors` 每次重绘都会被调一次 ⇒ 记下每次调用的时间戳与四门 alpha，
#   得到的是**精确的更新序列**（不是抽样）⇒ 不受采样率混叠影响。
#   同时缓存最后一次结果，探针自己不再重复调用（避免把自己的调用也算进去）。
_CACHE = {'got': []}
_WLOG = []
_orig_dsd = window._desktop_screen_doors


def _dsd_wrapped(sw, sh):
    got = _orig_dsd(sw, sh)
    try:
        _WLOG.append((time.time(), tuple(round(float(it[2]), 4) for it in got)))
        _CACHE['got'] = got
    except Exception:
        pass
    return got


window._desktop_screen_doors = _dsd_wrapped

_N = [0]
_t0 = time.time()
_tp = [None]
_rects = {}
_alpha = {}
_G = {'n': 0, 'ms': 0.0}
# ★ `EnumWindows` 一次要 50~100 ms，是 40 Hz 的**唯一**瓶颈（第一版实测只有 6.8 Hz）。
#   任务栏 z 名次不需要每帧都问 ⇒ 每 20 个样本刷一次（判据只看"是否发生翻转"，
#   20 样本 ≈ 0.7 s，足以抓到第116轮那种 5.7 Hz 的翻转序列）。
_TB = {'z': None, 'n': 0}


def tick():
    i = _N[0]
    now = time.time()
    el = now - _t0
    dt = 0.0 if _tp[0] is None else now - _tp[0]
    _tp[0] = now

    got = _CACHE['got']
    for it in (got or []):
        try:
            sid, r, a = str(it[0]), tuple(it[1]), float(it[2])
        except Exception:
            continue
        L = _LETTER_OF.get(sid)
        if not L:
            continue
        _rects[(L, 'r')] = r
        _rects[(L, 'sid')] = sid
        _alpha[L] = a

    g0 = time.time()
    _full = _grab_full()
    _G['n'] += 1
    _G['ms'] += (time.time() - g0) * 1000.0
    row = {'i': i, 't': '%.4f' % el, 'dt': '%.4f' % dt}
    for L in 'ABCD':
        r = _rects.get((L, 'r'))
        sid = _rects.get((L, 'sid'))
        if r is None or sid is None:
            continue
        row['%s_alpha' % L] = '%.4f' % _alpha.get(L, -1)
        try:
            x, y, w, h = [int(v) for v in r]
            sub = _full[max(0, y):y + h, max(0, x):x + w]
            if sub.size == 0:
                continue
            lum, crc, _n = _stat(sub, sid, w, h)
            row['%s_lum' % L] = '%.3f' % lum
            row['%s_crc' % L] = crc
        except Exception as e:                                   # noqa: BLE001
            say('统计 %s 失败 %r' % (L, e))
    if d is not None:
        row['dlg_op'] = '%.3f' % float(d.windowOpacity())
        row['dlg_vis'] = int(bool(d.isVisible()))
        g = d.geometry()
        row['dlg_y'], row['dlg_h'] = g.y(), g.height()
    if _TB['n'] % 20 == 0:
        _TB['z'] = _taskbar_z()
    _TB['n'] += 1
    row['tb_z'] = '' if _TB['z'] is None else _TB['z']
    _cw.writerow([row.get(c, '') for c in COLS])

    _N[0] += 1
    if el >= SECS:
        _csv.flush()
        _csv.close()
        el2 = time.time() - _t0
        say('采完 %d 样本 / %.2f s ⇒ **实测 %.1f Hz**（grab 均值 %.1f ms）'
            % (_N[0], el2, _N[0] / el2, _G['ms'] / max(1, _G['n'])))
        # ---- 写入路径序列（精确，不受采样率影响）----
        ws = list(_WLOG)
        say('写入路径：`_desktop_screen_doors` 被调 %d 次 / %.2f s ⇒ 重绘 %.1f Hz'
            % (len(ws), el2, len(ws) / max(1e-9, el2)))
        if ws:
            _w = io.open(os.path.join(OUT, 'fast117_writes.csv'), 'w',
                         encoding='utf-8', newline='')
            _ww = csv.writer(_w, lineterminator='\n')
            _ww.writerow(['k', 't'] + ['a%d' % j for j in range(len(ws[0][1]))])
            for k, (tt, al) in enumerate(ws):
                _ww.writerow([k, '%.4f' % (tt - _t0)] + list(al))
            _w.close()
            ch = [k for k in range(1, len(ws)) if ws[k][1] != ws[k - 1][1]]
            say('alpha 向量**变化** %d 次（共 %d 次调用）' % (len(ch), len(ws)))
            gaps = [ws[k][0] - ws[k - 1][0] for k in range(1, len(ws))]
            if gaps:
                gaps.sort()
                say('调用间隔 中位 %.1f ms / 最大 %.1f ms'
                    % (gaps[len(gaps) // 2] * 1000, gaps[-1] * 1000))
        app.quit()


_tm = QTimer()
_tm.timeout.connect(tick)
_tm.start(TICK_MS)
app.exec_()
say('done')
