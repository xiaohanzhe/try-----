# -*- coding: utf-8 -*-
u"""rec116.py —— 桌面门 / 对话框**真机录屏 + 逐帧取证**（回应用户「你自己录屏然后逐帧分析」）。

用户报告（逐字）
----------------
「门在闪现，黑底也没去干净，并且对话框也是闪现，而且，你门的形式也没用对」
「你自己录屏然后逐帧分析去」

本录制器要一次拿到四类证据
--------------------------
  ① **录像**（`rec116.avi`，mp4v 边抓边写，内存恒定）—— 人眼可直接看；
  ② **逐帧关键帧 PNG**（方向/尺寸/对话框矩形一变就落一张）；
  ③ **逐帧 CSV**：`对话框` 的 `opacity / visible / 矩形 / WS_EX_TOPMOST 位`，
     ★ 置顶位是本轮的核心判据 —— 只靠"几何不变"会得出"没闪"的**假结论**
       （本轮第一次就是这么被绕过去的：窗口 `geometry` 14 帧不变，
        可像素上那半个输入框在任务栏后面时隐时现）；
  ④ **对话框区域的**逐帧像素指纹（`mean/CRC`）—— "闪不闪"的客观量。

★ 沙箱：四闸（`RALSEI_MEMORY_DIR`/`RALSEI_DATA_DIR`/`RALSEI_DESKTOP`/`vault_root`）。
  跑完用 `_shared/vault_guard.py diff` 独立复核。

跑法
----
  set REC116_SECS=30
  C:\\Python311\\python.exe code-quality-audit\\第116轮-退出期崩溃定位与沙箱补漏\\_tools\\rec116.py
"""
import csv
import ctypes
import io
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
OUT = os.environ.get('REC116_OUT', os.path.join(ROUND, '_evidence', 'rec116'))
SECS = int(os.environ.get('REC116_SECS', '30'))
TICK_MS = int(os.environ.get('REC116_TICK_MS', '100'))
DRIVE = os.environ.get('REC116_DRIVE', '1') == '1'
os.makedirs(OUT, exist_ok=True)
FRAMES = os.path.join(OUT, 'frames')
os.makedirs(FRAMES, exist_ok=True)

# ---- 沙箱四闸（必须在 import main 之前）----
import tempfile                                                  # noqa: E402
_SB = tempfile.mkdtemp(prefix='rec116_')
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
import main as M                                                 # noqa: E402
from PyQt5.QtWidgets import QApplication                         # noqa: E402
from PyQt5.QtCore import QTimer, Qt, QPoint                      # noqa: E402


def say(m):
    sys.stdout.write('[rec116] %s\n' % m)
    sys.stdout.flush()


say('沙箱 = %s' % _SB)
M.check_single_instance()
M.install_crash_guard()
try:
    import text_segmenter
    text_segmenter.install()
    import jieba
    jieba.initialize()
except Exception:
    pass
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
_g = _scr.geometry()
_W, _H = _g.width(), _g.height()
say('shown pid=%d screen=%dx%d' % (os.getpid(), _W, _H))

# ---- Win32 小工具：拿"置顶位"与 z 序链 ----
# ★★★ 第116轮**踩到的真 bug**：原来只写 `ctypes.windll.user32.GetTopWindow(None)`，
#   而 ctypes 的**默认 restype 是 c_int（32 位）** ⇒ 64 位下 HWND 被**截断** ⇒
#   与 `int(winId())` 的完整 64 位句柄**永远不相等** ⇒ `dlg_z`/`taskbar_z`
#   两列**全空**（第一轮录制就是这个症状，光看数字看不出错）。
#   ⇒ 必须显式声明 `restype = c_void_p` / `argtypes`。
_U32 = ctypes.windll.user32
_U32.GetTopWindow.restype = ctypes.c_void_p
_U32.GetTopWindow.argtypes = [ctypes.c_void_p]
_U32.GetWindow.restype = ctypes.c_void_p
_U32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_U32.GetWindowLongW.restype = ctypes.c_long
_U32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
_U32.FindWindowW.restype = ctypes.c_void_p
_U32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
_U32.GetClassNameW.restype = ctypes.c_int
_U32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
_U32.IsWindowVisible.restype = ctypes.c_bool
_U32.IsWindowVisible.argtypes = [ctypes.c_void_p]
_WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                  ctypes.c_void_p)
_U32.EnumWindows.argtypes = [_WNDENUMPROC, ctypes.c_void_p]
_U32.EnumWindows.restype = ctypes.c_bool
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
HWNDPREV = 3
GW_HWNDPREV = 3


def _cls_of(h):
    u"""窗口类名（`Shell_TrayWnd` = 任务栏；`Qt5QWindowIcon` = Qt 窗口）。"""
    try:
        buf = ctypes.create_unicode_buffer(256)
        _U32.GetClassNameW(ctypes.c_void_p(h), buf, 256)
        return buf.value
    except Exception:
        return ''


def _ex_topmost(h):
    try:
        ex = _U32.GetWindowLongW(ctypes.c_void_p(h), GWL_EXSTYLE)
        return bool(int(ex) & WS_EX_TOPMOST)
    except Exception:
        return None


def _taskbar_hwnd():
    try:
        return int(_U32.FindWindowW(u'Shell_TrayWnd', None) or 0)
    except Exception:
        return 0


_TASKBAR = _taskbar_hwnd()


def _enum_top():
    u"""全部**顶层**窗口句柄，**按 z 序从顶到底**（`EnumWindows` 的天然顺序）。"""
    out = []

    def _cb(h, _lp):
        out.append(int(h))
        return True

    try:
        _U32.EnumWindows(_WNDENUMPROC(_cb), None)
    except Exception:
        pass
    return out


def _z_stack(limit=400, visible_only=False):
    u"""桌面 z 序链（最顶在前）`[(hwnd, class), ...]`。

    ★★★ 第116轮**第二个**踩到的坑：最初用
      `GetTopWindow(NULL)` + `GetWindow(h, GW_HWNDPREV)` 往下走 —— 实测这条
      走法**根本走不动**：真机打出 `z_stack_top30` 只有 **1 条**
      （`MSCTFIME UI`，一个 IME 的**子**窗口）⇒ 我们自己的窗口永远查不到名次
      ⇒ `dlg_z`/`taskbar_z` 两列**恒空**。
      （叠加的第一个坑是 ctypes 默认 `restype=c_int` 把 64 位 HWND 截断。）
      ⇒ 正确走法 = **`EnumWindows`**：它按 z 序从顶到底枚举**顶层**窗口。
    """
    out = []
    for h in _enum_top():
        if len(out) >= limit:
            break
        if visible_only and not _U32.IsWindowVisible(ctypes.c_void_p(h)):
            continue
        out.append((h, _cls_of(h)))
    return out


def _win_visible(h):
    try:
        return bool(_U32.IsWindowVisible(ctypes.c_void_p(h)))
    except Exception:
        return None


def _z_index(h, stack=None):
    """链上名次（越小越靠上）；找不到 ⇒ `None`。"""
    st = stack if stack is not None else _z_stack()
    for i, (hh, _c) in enumerate(st):
        if hh == h:
            return i
    return None


# ---- 找对话框 ----
_dlg = None
for _nm in ('dialogue_ui', 'dialog_ui', 'dialogue_box'):
    if getattr(window, _nm, None) is not None:
        _dlg = getattr(window, _nm)
        break
say('dialogue_ui = %r' % (type(_dlg).__name__ if _dlg else None))

_t0 = time.time()
_N = [0]
_KEY = [0]
_LASTKEY = [None]
RAW = os.path.join(OUT, 'rec116.avi')
_vw = cv2.VideoWriter(RAW, cv2.VideoWriter_fourcc(*'mp4v'),
                      1000.0 / TICK_MS, (_W, _H))
if not _vw.isOpened():
    say('FATAL VideoWriter 打不开')
    sys.exit(2)

_csv = io.open(os.path.join(OUT, 'rec116_frames.csv'), 'w',
               encoding='utf-8', newline='')
_cw = csv.writer(_csv, lineterminator='\n')
_cw.writerow(['i', 't', 'tw', 'dlg_op', 'dlg_vis', 'dlg_wv', 'dlg_x', 'dlg_y',
              'dlg_w', 'dlg_h', 'dlg_top', 'dlg_z', 'taskbar_z', 'dlg_above_tb',
              'above_dlg', 'above_tb',
              'pet_x', 'pet_y', 'pet_w', 'pet_h',
              'region_mean', 'region_crc', 'pet_below_taskbar',
              'dN', 'dA', 'dB', 'dC', 'dD'])
_GRAB = [0.0]
_ENC = [0.0]

# ★ 贴图名 → 门字母（用于把 `_desktop_screen_doors()` 的输出还原成 A/B/C/D）
_LETTER_OF = {
    'objs/spr_darkdoor_0.png': 'A',
    'objs/niko_door_portal.png': 'B',
    'objs/ut_castle_realdoor_0.png': 'C',
    'objs/spr_giantdarkdoor_0.png': 'D',
}
_DOOR_RECTS = {}


def _doors_now():
    u"""读产品**当前帧**的屏幕层门 `[(sprite, rect, alpha)]` ⇒ `({letter: alpha}, n)`。

    ★ 这一列是本轮验证的**核心**：门渐显（`door_reveal` 写的 alpha）有没有真的
      走到屏幕层。`alpha` 恒 1.0 ⇒ 修复无效（C/D 还是实心黑块）。
    ★ 只读、不改状态；任何异常 ⇒ 空（**不许让取证脚本自己把被测物搞崩**）。
    """
    al = {}
    try:
        got = window._desktop_screen_doors(_W, _H)
    except Exception:
        return al, 0
    for it in (got or []):
        try:
            sid = str(it[0])
            r = it[1]
            a = float(it[2]) if len(it) >= 3 else 1.0
        except Exception:
            continue
        L = _LETTER_OF.get(sid, sid)
        al[L] = a
        _DOOR_RECTS[L] = tuple(r)
    return al, len(got or [])


def tick():
    i = _N[0]
    try:
        tg = time.time()
        pm = _scr.grabWindow(0)
        img = pm.toImage()
        ptr = img.bits()
        ptr.setsize(img.byteCount())
        raw = bytes(ptr)
        arr = np.frombuffer(raw, np.uint8).reshape(
            img.height(), img.bytesPerLine() // 4, 4)
        arr = np.ascontiguousarray(arr[:, :img.width(), :3])
        _GRAB[0] += (time.time() - tg) * 1000.0
        te = time.time()
        _vw.write(arr)
        _ENC[0] += (time.time() - te) * 1000.0

        row = {'i': i, 't': '%.3f' % (time.time() - _t0),
               'tw': '%.4f' % time.perf_counter()}
        d = _dlg
        if d is not None:
            row['dlg_op'] = '%.3f' % float(d.windowOpacity())
            row['dlg_vis'] = int(bool(d.isVisible()))
            gg = d.geometry()
            row['dlg_x'] = gg.x()
            row['dlg_y'] = gg.y()
            row['dlg_w'] = gg.width()
            row['dlg_h'] = gg.height()
            h = 0
            try:
                h = int(d.winId())
            except Exception:
                pass
            row['dlg_top'] = int(bool(_ex_topmost(h)))
            # ★ `IsWindowVisible`（Win32）—— 透明分层窗口下屏幕工具会失效，
            #   这条是"窗口到底 visible 没有"的独立口径（见契约⑤）。
            row['dlg_wv'] = int(bool(_win_visible(h)))
            # ★★★ 第116轮核心判据：**一次快照**整条 z 序链，再查名次。
            #   只靠"几何不变"会得出"没闪"的**假结论** —— 本轮第一次就是被
            #   这个绕过去的（窗口 geometry 14 帧不变，可像素上输入框在任务栏
            #   后面时隐时现）。真正决定"看得见看不见"的是**名次**。
            _st = _z_stack(120)
            row['dlg_z'] = _z_index(h, _st)
            row['taskbar_z'] = _z_index(_TASKBAR, _st)
            _dz = row.get('dlg_z')
            _tz = row.get('taskbar_z')
            row['dlg_above_tb'] = (
                int(_dz < _tz) if (_dz is not None and _tz is not None) else '')
            # 谁**紧贴在对话框上方**（= 实际盖住它的那个窗口）
            row['above_dlg'] = ''
            if _dz is not None and _dz > 0:
                row['above_dlg'] = _st[_dz - 1][1]
            # 紧贴在任务栏上方的是谁
            row['above_tb'] = ''
            if _tz is not None and _tz > 0:
                row['above_tb'] = _st[_tz - 1][1]
            x, y, w, hh = gg.x(), gg.y(), gg.width(), gg.height()
        else:
            x, y, w, hh = 0, 0, 1, 1
        row['pet_x'] = window.x()
        row['pet_y'] = window.y()
        row['pet_w'] = window.width()
        row['pet_h'] = window.height()
        # ★★★ 第116轮核心列：屏幕层门的 alpha（A/B 应恒 1.0；C/D 应随距离变虚）
        _al, _n = _doors_now()
        row['dN'] = _n
        for _L in 'ABCD':
            row['d' + _L] = '%.3f' % _al[_L] if _L in _al else ''
        x0 = max(0, min(_W - 1, x))
        y0 = max(0, min(_H - 1, y))
        x1 = max(x0 + 1, min(_W, x + w))
        y1 = max(y0 + 1, min(_H, y + hh))
        crop = arr[y0:y1:4, x0:x1:4]           # 4 倍降采样，够做指纹
        row['region_mean'] = '%.3f' % float(crop.mean())
        row['region_crc'] = '%08x' % (int(crop.sum()) & 0xFFFFFFFF)
        row['pet_below_taskbar'] = int(
            (row.get('pet_x') or 0) + (row.get('pet_w') or 0) > 0)
        _cw.writerow([row.get(k, '') for k in (
            'i', 't', 'tw', 'dlg_op', 'dlg_vis', 'dlg_wv', 'dlg_x', 'dlg_y',
            'dlg_w', 'dlg_h', 'dlg_top', 'dlg_z', 'taskbar_z', 'dlg_above_tb',
            'above_dlg', 'above_tb',
            'pet_x', 'pet_y', 'pet_w', 'pet_h',
            'region_mean', 'region_crc', 'pet_below_taskbar',
            'dN', 'dA', 'dB', 'dC', 'dD')])

        # 关键帧：对话框矩形 / 透明度 / 宠物矩形 一变就落一张裁图
        key = (row['dlg_x'], row['dlg_y'], row['dlg_w'], row['dlg_h'],
               row['dlg_op'], row['pet_x'], row['pet_y'])
        if key != _LASTKEY[0]:
            _LASTKEY[0] = key
            pad = 24
            cx0 = max(0, x0 - pad)
            cy0 = max(0, y0 - pad)
            cx1 = min(_W, x1 + pad)
            cy1 = min(_H, y1 + pad)
            c = np.ascontiguousarray(arr[cy0:cy1, cx0:cx1])
            if c.size:
                ok, buf = cv2.imencode('.png', c)
                if ok:
                    with open(os.path.join(FRAMES, 'k%06d.png' % _KEY[0]),
                              'wb') as fh:
                        fh.write(buf.tobytes())
                    _KEY[0] += 1
        _csv.flush()
    except Exception:
        sys.stdout.write('TICK-ERR\n' + traceback.format_exc() + '\n')
        sys.stdout.flush()
    _N[0] = i + 1


tm = QTimer()
tm.timeout.connect(tick)

# 驱动器：把宠物在桌面上四个方向走一遍（覆盖"移动时"的场景）
if DRIVE:
    _POS = [(120, 120), (_W - 300, 120), (_W - 300, _H - 420),
            (120, _H - 420)]
    _st = {'i': -1}

    def _drive():
        _st['i'] = (_st['i'] + 1) % len(_POS)
        tx, ty = _POS[_st['i']]
        try:
            window.target_pos = QPoint(int(tx), int(ty))
            window.is_moving = True
            window.is_sleeping = False
            say('DRIVE => target=(%d,%d) from=(%d,%d)'
                % (tx, ty, window.x(), window.y()))
        except Exception:
            say('DRIVE fail\n' + traceback.format_exc())

    _tm2 = QTimer()
    _tm2.timeout.connect(_drive)
    _tm2.start(5000)
    QTimer.singleShot(600, _drive)


def _finish():
    tm.stop()
    _vw.release()
    _csv.close()
    dur = time.time() - _t0
    with io.open(os.path.join(OUT, 'rec116_meta.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(u'secs=%d tick_ms=%d frames=%d keypng=%d wall=%.1fs\n'
                 % (SECS, TICK_MS, _N[0], _KEY[0], dur))
        fh.write(u'grab_ms_total=%.0f enc_ms_total=%.0f\n' % (_GRAB[0], _ENC[0]))
        fh.write(u'screen=%dx%d sandbox=%s\n' % (_W, _H, _SB))
        fh.write(u'taskbar_hwnd=%d\n' % _TASKBAR)
        fh.write(u'door_rects=%r\n' % _DOOR_RECTS)
        fh.write(u'z_stack_top30=%r\n' % _z_stack(30))
    say('done frames=%d keypng=%d wall=%.1fs' % (_N[0], _KEY[0], dur))
    app.quit()


tm.start(TICK_MS)
QTimer.singleShot(SECS * 1000, _finish)

if __name__ == '__main__':
    rc = app.exec_()
    try:
        tm.stop()
        _vw.release()
        _csv.close()
    except Exception:
        pass
    say('exit rc=%d' % rc)
    sys.exit(rc)
