# -*- coding: utf-8 -*-
u"""probe116_doors.py —— 桌面 4 扇门：**内省 + 像素**双通道探针（v2，只读）。

v1 的两个教训（同一轮抓到，都已修）
-----------------------------------
1. **CSV 逗号错位**：v1 手写 `','.join(...)`，而 `pet` / `ent` / `req` / `rX`
   这些字段**内部就含逗号**（`'430,60,39,83'`）⇒ 表头 28 列、数据 48 列
   ⇒ 之后按下标读列**全是错的**。★ 改用 `csv.writer`（会自动加引号）。
2. **抓屏只有 4.8 Hz**：`QScreen.grabWindow(0, x,y,w,h)` 在 Windows 上仍要走
   DWM 合成，一次 ~26ms，一 tick 8 次 ⇒ 208 ms/tick ⇒ 面对 ~2~10 Hz 的闪
   **必然混叠**。⇒ v2 改成**产品内省为主**（给 `SceneCanvas.paintEvent` /
   `_paint_screen_doors` 挂**透明**记录器，拿产品原生帧率），像素只作粗校验。

本探针一次回答四个问题
----------------------
  Q1 **门层每帧到底画了没有**：每次 `paintEvent` 记 `(t, 画了几扇, 逐门 alpha,
     画布 isVisible, opaque_bg, transition_alpha)`。⇒ `画了=4 且 alpha 恒定`
     ⇒ **门自己没闪**；此时若屏幕像素仍在跳，闪**只能来自遮挡物**。
  Q2 **画布有没有被隐藏**：`paintEvent` 不跑 = 整层没了（`has_screen_doors`
     那条判据若失效，画布会被 `_hide_scene_layer()` 藏掉）。
  Q3 **渐显接没接到"实体"**：扫描宠物 ⇒ `alpha` 是否随距离变。
  Q4 **遮挡**：门矩形里到底是谁的像素（任务栏 / 气泡 / 对话框）。

跑法
----
  set PROBE_SECS=40 && set PROBE_SWEEP=1
  C:\\Python311\\python.exe "...\\_tools\\probe116_doors.py"
"""
import csv
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

SECS = float(os.environ.get('PROBE_SECS') or '30')
HZ = float(os.environ.get('PROBE_HZ') or '10')
DOUBLE = os.environ.get('PROBE_DOUBLE', '1') == '1'
SWEEP = os.environ.get('PROBE_SWEEP', '0') == '1'
SWEEP_MS = float(os.environ.get('PROBE_SWEEP_MS') or '6000')
TAG = os.environ.get('PROBE_TAG') or 'doors'

# ---- 沙箱四闸（必须在 import main 之前）----
_SB = tempfile.mkdtemp(prefix='probe116d_')
for _s in ('vault', 'staging', 'desktop'):
    os.makedirs(os.path.join(_SB, _s), exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(_SB, 'vault')
os.environ['RALSEI_DATA_DIR'] = os.path.join(_SB, 'staging')
os.environ['RALSEI_DESKTOP'] = os.path.join(_SB, 'desktop')
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')
os.chdir(PKG)
sys.path.insert(0, SRC)

import numpy as np                                            # noqa: E402
import main as M                                              # noqa: E402
from PyQt5.QtWidgets import QApplication                      # noqa: E402
from PyQt5.QtCore import QTimer, QPoint                       # noqa: E402
import scene_canvas as SC                                      # noqa: E402


def say(m):
    sys.stdout.write('[probe116d] %s\n' % m)
    sys.stdout.flush()


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
_W, _H = _scr.geometry().width(), _scr.geometry().height()
_CANVAS = getattr(window, 'scene_canvas', None)
say('pid=%d screen=%dx%d canvas=%r sandbox=%s'
    % (os.getpid(), _W, _H, type(_CANVAS).__name__ if _CANVAS else None, _SB))

# ★★★ 贴图名 → 门字母。**必须按 `desktop.json` 现读**，不能写死：
#   第116轮就是写死这张表，而本轮把门 C/D 的贴图换成了桌面变体
#   （`desk_door_ut.png` / `desk_door_deltarune.png`）⇒ 映射**静默失效**
#   ⇒ 主 CSV 里 `aC/aD/xC/...` 整批为空，而分析器只是"跳过该门"（不报红）
#   ⇒ **判据崩掉比报红更糟**的经典形态。现改成：先读 `desktop.json` 建表，
#   读不到才退回写死的旧表；且建表后在报告里**逐门点名**缺了哪几扇。
_LETTER_OF_FALLBACK = {
    'objs/spr_darkdoor_0.png': 'A',
    'objs/niko_door_portal.png': 'B',
    'objs/ut_castle_realdoor_0.png': 'C',
    'objs/spr_giantdarkdoor_0.png': 'D',
}


def _letter_map():
    u"""`{sprite: letter}` —— 从 `desktop.json` 现读（单一真源）。"""
    m = dict(_LETTER_OF_FALLBACK)
    try:
        import json
        p = os.path.join(PKG, 'assets', 'scenes', 'desktop.json')
        d = json.load(io.open(p, encoding='utf-8'))
        for o in d.get('objects', []):
            if not isinstance(o, dict):
                continue
            L = door_letter(o.get('src'))
            nm = o.get('sprite') or o.get('image')
            if L and isinstance(nm, str) and nm:
                m[nm] = L
    except Exception as e:
        say('建字母表失败（退回写死表）: %r' % (e,))
    return m


def door_letter(src):
    u"""`obj_doorC` → `'C'`（与产品 `door_reveal.door_letter_of_local` 同构）。"""
    if not isinstance(src, str):
        return None
    s = src.strip()
    if not s.lower().startswith('obj_door'):
        return None
    head = s[len('obj_door'):].split('_', 1)[0]
    return head.upper() if len(head) == 1 else None


_LETTER_OF = _letter_map()
say('字母表 = %r' % (_LETTER_OF,))
TASKBAR_IN = int(os.environ.get('PROBE_TASKBAR_IN') or '64')
IN2 = int(os.environ.get('PROBE_IN2') or '3')

_T0 = time.perf_counter()
_PLOG = []          # 每次 paintEvent 一条
_DLOG = []          # 每次 _paint_screen_doors 一条


def _wrap_paint():
    u"""给**活画布的类**挂透明记录器。

    ★★★ 教训（本轮踩到）：第一版写 `SC.SceneCanvas.paintEvent = _pe`，
      结果 `内省 paintEvent 次数 = 0` —— 因为 `main` 里的画布是从
      **另一个模块名**引的类（`modules.scene_canvas` vs `scene_canvas`），
      `SC.SceneCanvas` 与 `type(window.scene_canvas)` **不是同一个类对象**
      ⇒ 补丁打在了没人用的那份上。⇒ 一律按 `type(活对象)` 打补丁。
    ★ 透明 = 原样调用、原样返回、不吞异常、不改状态；只把"这一帧画了什么"追加
      进内存列表。★ 为什么不改产品代码打点：那会让**被测物**带上取证代码
      （本项目已踩过"录制器自己制造伪影"）。
    """
    _CLS = type(_CANVAS)
    _orig_pe = _CLS.paintEvent
    _orig_psd = _CLS._paint_screen_doors
    say('补丁目标类 = %r' % (_CLS,))

    def _pe(self, event):
        t = time.perf_counter() - _T0
        try:
            vis = int(bool(self.isVisible()))
            opq = int(bool(getattr(self, '_opaque_bg', False)))
            tra = float(getattr(self, '_transition_alpha', 0.0) or 0.0)
            nd = len(getattr(self, '_screen_doors', []) or [])
            w = self.width()
            h = self.height()
        except Exception:
            vis, opq, tra, nd, w, h = -1, -1, -1.0, -1, -1, -1
        ld = None
        try:
            return _orig_pe(self, event)
        finally:
            # ★ 不用 `or -1`：`last_drawn == 0` 是**有意义的值**
            #   （这一帧房间层+屏幕层**都没画出东西**）——坑过一版判据。
            try:
                ld = int(getattr(self, 'last_drawn', -1))
            except Exception:
                ld = -1
            _PLOG.append((t, vis, opq, round(tra, 3), nd, w, h, ld))

    def _psd(self, painter):
        t = time.perf_counter() - _T0
        try:
            al = []
            for it in (getattr(self, '_screen_doors', []) or []):
                try:
                    al.append(round(float(it[2]), 4))
                except Exception:
                    al.append(-1.0)
        except Exception:
            al = []
        try:
            n = _orig_psd(self, painter)
        except Exception:
            _DLOG.append((t, len(al), tuple(al), -999))
            raise
        _DLOG.append((t, len(al), tuple(al), n))
        return n

    _CLS.paintEvent = _pe
    _CLS._paint_screen_doors = _psd


_wrap_paint()
say('已挂内省（paintEvent / _paint_screen_doors）')


def _door_state():
    u"""读产品当前帧的屏幕层门 ⇒ `({letter: (rect, alpha)}, n)`。**只读**。"""
    d = {}
    try:
        got = window._desktop_screen_doors(_W, _H)
    except Exception:
        return d, 0
    for it in (got or []):
        try:
            sid = str(it[0])
            r = tuple(int(v) for v in it[1])
            a = float(it[2]) if len(it) >= 3 else 1.0
        except Exception:
            continue
        d[_LETTER_OF.get(sid, sid)] = (r, a)
    return d, len(got or [])


def _inner(letter, r):
    x, y, w, h = r
    x0, y0 = x + IN2, y + IN2
    x1, y1 = x + w - IN2, y + h - IN2
    if letter == 'B':
        y1 -= TASKBAR_IN
    x0 = max(0, min(_W - 1, x0))
    y0 = max(0, min(_H - 1, y0))
    x1 = max(x0 + 1, min(_W, x1))
    y1 = max(y0 + 1, min(_H, y1))
    return x0, y0, x1 - x0, y1 - y0


def _frac(px):
    img = px.toImage()
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    a = np.frombuffer(bytes(ptr), np.uint8).reshape(
        img.height(), img.bytesPerLine() // 4, 4)
    a = np.ascontiguousarray(a[:, :img.width(), :3])
    return float((a.max(axis=2) < 16).mean()), float(a.mean())


# ---- Win32：z 序（EnumWindows 是唯一可靠走法；见 rec116 的教训）----
_U32 = ctypes.windll.user32
_U32.EnumWindows.restype = ctypes.c_bool
_WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                  ctypes.c_void_p)
_U32.EnumWindows.argtypes = [_WNDENUMPROC, ctypes.c_void_p]
_U32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
_U32.FindWindowW.restype = ctypes.c_void_p
_U32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]


def _cls_of(h):
    try:
        buf = ctypes.create_unicode_buffer(256)
        _U32.GetClassNameW(ctypes.c_void_p(h), buf, 256)
        return buf.value
    except Exception:
        return ''


def _z_index(hwnd):
    u"""画布句柄在顶层 z 序链上的名次（越小越靠上）；找不到 ⇒ -1。"""
    out = []

    def _cb(h, _lp):
        out.append(int(h))
        return True
    try:
        _U32.EnumWindows(_WNDENUMPROC(_cb), None)
    except Exception:
        return -1
    for i, x in enumerate(out):
        if x == hwnd:
            return i
    return -1


_TB = 0
try:
    _TB = int(_U32.FindWindowW(u'Shell_TrayWnd', None) or 0)
except Exception:
    pass

_SWEEP_KEY = [(_W // 2, 60), (20, 60), (20, _H // 2 - 120), (20, _H - 420),
              (_W - 240, _H - 420), (_W - 240, _H // 2 - 120),
              (_W - 240, 60), (_W // 2, 60)]


def _sweep_pos(t):
    n = len(_SWEEP_KEY)
    seg = (t / max(0.05, SWEEP_MS / 1000.0)) % n
    i = int(seg) % n
    f = seg - int(seg)
    x0, y0 = _SWEEP_KEY[i]
    x1, y1 = _SWEEP_KEY[(i + 1) % n]
    return (int(x0 + (x1 - x0) * f), int(y0 + (y1 - y0) * f))


_rows = []
_N = [0]
_RECTS = {}


def tick():
    i = _N[0]
    t = time.perf_counter() - _T0
    row = {'i': i, 't': round(t, 4)}
    try:
        if SWEEP:
            rx, ry = _sweep_pos(t)
            row['req_x'], row['req_y'] = rx, ry
            try:
                window.move(int(rx), int(ry))
            except Exception:
                pass
        ds, nd = _door_state()
        row['nd'] = nd
        row['desk'] = int(bool(window._scene_is_desktop_scene()))
        row['opqbg'] = int(bool(getattr(_CANVAS, '_opaque_bg', False)))
        row['cvis'] = int(bool(_CANVAS.isVisible())) if _CANVAS else -1
        row['last_drawn'] = int(getattr(_CANVAS, 'last_drawn', -1) or -1)
        for L in 'ABCD':
            if L in ds:
                r, a = ds[L]
                _RECTS[L] = r
                row['a' + L] = round(a, 4)
                for j, nm in enumerate('xywh'):
                    row['%s%s' % (nm, L)] = r[j]
        # ★ 像素只作粗校验：D（最大的黑块）每 tick，B 每 3 tick
        #   （`grabWindow` 一次 ~26ms，抓太多会把 tick 拖到 150ms ⇒ 混叠）
        if 'D' in ds:
            b, m = _frac(_scr.grabWindow(0, *_inner('D', ds['D'][0])))
            row['bD'] = round(b, 4)
            row['mD'] = round(m, 2)
        if 'B' in ds and i % 3 == 0:
            b, m = _frac(_scr.grabWindow(0, *_inner('B', ds['B'][0])))
            row['bB'] = round(b, 4)
            row['mB'] = round(m, 2)
        try:
            row['ent'] = ';'.join('%.1f' % v
                                  for v in window._camera_target_rect(
                                      (0.0, 0.0, 320.0, 240.0)))
        except Exception:
            row['ent'] = ''
        try:
            row['soul'] = int(bool(window._soul_visible()))
            sc = window.soul.state.center()
            row['soulxy'] = '%d;%d' % (int(sc[0]), int(sc[1]))
        except Exception:
            row['soulxy'] = ''
        row['pet'] = '%d;%d;%d;%d' % (window.x(), window.y(),
                                      window.width(), window.height())
        try:
            row['k'] = round(float(getattr(window, '_cached_scale_factor', 0)
                                   or 0.0), 4)
        except Exception:
            row['k'] = 0.0
        try:
            if i % 5 == 0:
                row['cz'] = _z_index(int(_CANVAS.winId()))
                row['tbz'] = _z_index(_TB)
                row['c_above_tb'] = int(row['cz'] < row['tbz']) if (
                    row['cz'] >= 0 and row['tbz'] >= 0) else ''
            else:
                row['cz'] = row['tbz'] = row['c_above_tb'] = ''
        except Exception:
            row['c_above_tb'] = ''
    except Exception as e:
        row['err'] = repr(e)
    _rows.append(row)
    _N[0] = i + 1


tm = QTimer()
tm.timeout.connect(tick)
tm.start(max(1, int(1000.0 / HZ)))

_DRV_LOG = []

if not SWEEP:
    _POS = [(20, _H // 2 - 120), (_W - 240, _H // 2 - 120),
            (_W // 2 - 120, _H // 2 - 120), (_W // 2 - 120, 20),
            (20, _H - 420), (_W - 240, _H - 420)]
    _stt = {'i': -1}

    def _drive():
        _stt['i'] = (_stt['i'] + 1) % len(_POS)
        tx, ty = _POS[_stt['i']]
        try:
            window.target_pos = QPoint(int(tx), int(ty))
            window.is_moving = True
            window.is_sleeping = False
            _DRV_LOG.append((round(time.perf_counter() - _T0, 3), tx, ty,
                             window.x(), window.y()))
        except Exception as e:
            _DRV_LOG.append(('FAIL', repr(e)))

    _tm2 = QTimer()
    _tm2.timeout.connect(_drive)
    _tm2.start(4000)
    QTimer.singleShot(600, _drive)


def _srt(vals, limit=None):
    u"""**类型安全**去重 + 排序。

    ★★★ 教训（本轮踩到，直接导致"两个 CSV 写了、报告和截图没了"）：
      `sorted(set(...))` 在**混合类型**上抛 `TypeError: '<' not supported
      between instances of 'int' and 'str'`。本探针里至少两处天然混型：
        · `c_above_tb` —— 有值行是 `int`，`i%5!=0` 的行是 `''`
        · `_DLOG` 第 4 项 —— 正常是 `int`（画了几扇），
          原函数抛异常时是 `-999`，返回 None 时是 `None`
      而 `_finish()` 是**先写 CSV、后拼报告** ⇒ 异常发生在拼报告阶段
      ⇒ 盘上只剩两个 CSV，`*.txt` 与截图**全丢**。
    ⇒ 一律按 `(类型名, repr)` 排序；显示时 `limit` 截断。
    """
    uniq = {}
    for v in vals:
        uniq.setdefault((type(v).__name__, repr(v)), v)
    out = [uniq[k] for k in sorted(uniq)]
    return out[:limit] if limit else out


def _finish():
    tm.stop()
    rep = []
    try:
        _finish_report(rep)
    except Exception:
        import traceback
        rep.append(u'✗✗✗ _finish_report 中途异常（CSV 可能已落盘）：')
        rep.append(traceback.format_exc())
    txt = u'\n'.join(rep) + u'\n'
    with io.open(os.path.join(OUT, 'probe116_%s.txt' % TAG), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    say(txt)
    app.quit()


def _finish_report(rep):
    # ---- 主 CSV（csv.writer 会自动给含逗号的字段加引号）----
    keys = ['i', 't', 'nd', 'desk', 'opqbg', 'cvis', 'last_drawn', 'k',
            'soul', 'soulxy', 'req_x', 'req_y', 'ent', 'pet',
            'cz', 'tbz', 'c_above_tb']
    for L in 'ABCD':
        keys += ['a' + L, 'x' + L, 'y' + L, 'w' + L, 'h' + L]
    keys += ['bB', 'mB', 'bB2', 'bD', 'mD', 'bD2', 'err']
    keys = [k for k in keys if any(k in r for r in _rows)]
    with io.open(os.path.join(OUT, 'probe116_%s.csv' % TAG), 'w',
                 encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction='ignore',
                           lineterminator='\n')
        w.writeheader()
        for r in _rows:
            w.writerow(r)
    # ---- 内省 CSV ----
    with io.open(os.path.join(OUT, 'probe116_%s_paint.csv' % TAG), 'w',
                 encoding='utf-8', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['t', 'cvis', 'opqbg', 'tra', 'doors_len', 'w', 'h',
                    'last_drawn', 'psd_n', 'n_list', 'alphas'])
        _pm = {}
        for t, n, al, ret in _DLOG:
            _pm.setdefault(round(t, 2), []).append((n, al, ret))
        for row in _PLOG:
            t, vis, opq, tra, nd, w_, h_, ld = row
            g = _pm.get(round(t, 2)) or []
            w.writerow([round(t, 4), vis, opq, tra, nd, w_, h_, ld,
                        g[0][2] if g else '', g[0][0] if g else '',
                        g[0][1] if g else ''])

    # ---- 摘要 ----
    rep.append(u'# probe116_doors v2  tag=%s  n=%d  目标 %.0f Hz  实测 %.1f Hz'
               % (TAG, len(_rows), HZ, len(_rows) / max(1e-9, _rows[-1]['t'])))
    rep.append(u'门矩形（产品口径） = %r' % (_RECTS,))
    rep.append(u'★ 内省 paintEvent 次数 = %d   期间 = %.1f s  ⇒ %.1f 次/s'
               % (len(_PLOG), _PLOG[-1][0] if _PLOG else 0,
                  len(_PLOG) / max(1e-9, _PLOG[-1][0] if _PLOG else 1)))
    for k, nm in (('nd', u'门清单长度'), ('cvis', u'画布 isVisible'),
                  ('opqbg', u'opaque_bg'), ('desk', u'桌面场景'),
                  ('last_drawn', u'last_drawn'), ('c_above_tb', u'画布在任务栏之上')):
        if any(k in r for r in _rows):
            rep.append(u'%s 取值集合 = %s'
                       % (nm, _srt((r.get(k) for r in _rows), 12)))
    for k, nm in (('soul', u'灵魂可见'), ('soulxy', u'灵魂位置'),
                  ('ent', u'实体锚点(房间)'), ('pet', u'宠物矩形')):
        if any(k in r for r in _rows):
            rep.append(u'%s 取值集合(前6) = %s'
                       % (nm, _srt((r.get(k) for r in _rows), 6)))
    for L in 'ABCD':
        v = [r['a' + L] for r in _rows if ('a' + L) in r]
        if v:
            a = np.array(v, dtype=float)
            rep.append(u'门%s alpha  min=%.3f max=%.3f 中位=%.3f 极差=%.3f'
                       % (L, a.min(), a.max(), float(np.median(a)),
                          float(a.max() - a.min())))
    # ★★★ 决定性判据：alpha 与「宠物 ↔ 门的**屏幕像素间距**」
    for L in 'ABCD':
        pairs = []
        for r in _rows:
            if ('a' + L) not in r or 'pet' not in r or ('x' + L) not in r:
                continue
            try:
                px, py, pw, ph = [int(v) for v in r['pet'].split(';')]
                x, y = r['x' + L], r['y' + L]
                dw, dh = r['w' + L], r['h' + L]
            except Exception:
                continue
            gapx = max(x - (px + pw), px - (x + dw), 0)
            gapy = max(y - (py + ph), py - (y + dh), 0)
            pairs.append(((gapx * gapx + gapy * gapy) ** 0.5, r['a' + L]))
        if not pairs:
            continue
        g = np.array([p[0] for p in pairs], dtype=float)
        al = np.array([p[1] for p in pairs], dtype=float)
        rep.append(u'门%s 屏幕间距 n=%d min=%.0f max=%.0f 极差=%.0f px | '
                   u'alpha 极差=%.3f' % (L, len(pairs), g.min(), g.max(),
                                         g.max() - g.min(),
                                         float(al.max() - al.min())))
        if g.max() - g.min() > 50:
            _near = al[g <= 220]
            _far = al[g >= 700]
            if len(_near) and len(_far):
                rep.append(u'    ★ 贴门 alpha 中位=%.3f(n=%d)  远离 alpha 中位'
                           u'=%.3f(n=%d)  ⇒ %s'
                           % (float(np.median(_near)), len(_near),
                              float(np.median(_far)), len(_far),
                              u'随距离渐变（渐显已接通）'
                              if abs(float(np.median(_far))
                                     - float(np.median(_near))) > 0.05
                              else u'**恒定 ⇒ 渐显没接到宠物（真因）**'))
            else:
                rep.append(u'    ⚠ 未覆盖贴门/远离两端 ⇒ 本项不作结论')
    # ★ 内省：逐帧 alpha / 门数 / 实际画了几扇
    if _DLOG:
        ns = _srt(d[1] for d in _DLOG)
        rs = _srt(d[3] for d in _DLOG)
        rep.append(u'★ 内省 _paint_screen_doors 调用 %d 次；清单门数集合 = %s；'
                   u'实际画出扇数集合 = %s' % (len(_DLOG), ns, rs))
        als = sorted(set(d[2] for d in _DLOG))
        rep.append(u'★ 内省 逐帧 alpha 元组种数 = %d（种数=1 ⇒ 整段恒定）' % len(als))
        for a in als[:6]:
            rep.append(u'    %s' % (a,))
    if _PLOG:
        lds = [r[7] for r in _PLOG]
        rep.append(u'★ 内省 last_drawn 取值集合 = %s（0 = 这一帧**一扇门都没画**）'
                   % (sorted(set(lds))[:12],))
        rep.append(u'★ 内省 画布 isVisible 取值集合 = %s'
                   % (sorted(set(r[1] for r in _PLOG))[:6],))
        gaps = [round(_PLOG[j][0] - _PLOG[j - 1][0], 4)
                for j in range(1, len(_PLOG))]
        if gaps:
            ga = np.array(gaps, dtype=float)
            rep.append(u'★ 内省 帧间隔：中位 %.4f s  最大 %.4f s  '
                       u'（最大 > 3×中位 ⇒ 有卡顿）'
                       % (float(np.median(ga)), float(ga.max())))
            big = [j for j in range(1, len(_PLOG))
                   if _PLOG[j][0] - _PLOG[j - 1][0] > 0.5]
            rep.append(u'★ 内省 帧间隔 > 0.5s 的位置 = %s'
                       % ([(round(_PLOG[j][0], 2), _PLOG[j][7],
                           _PLOG[j][1]) for j in big][:8],))
    for L in ('B', 'D'):
        v = [r['b' + L] for r in _rows if ('b' + L) in r]
        if v:
            a = np.array(v, dtype=float)
            thr = 0.5 * (float(a.min()) + float(a.max()))
            z = int(np.sum(np.abs(np.diff((a > thr).astype(int))) > 0))
            rep.append(u'门%s 纯黑比 min=%.3f max=%.3f 中位=%.3f 过零=%d'
                       % (L, a.min(), a.max(), float(np.median(a)), z))
            k2 = 'b' + L + '2'
            if any(k2 in r for r in _rows):
                d = np.array([abs(r['b' + L] - r[k2])
                              for r in _rows if k2 in r], dtype=float)
                rep.append(u'    同刻两次 |Δ|= 中位 %.4f 最大 %.4f'
                           % (float(np.median(d)), float(d.max())))
    # ★★★ 肉眼证据：跑完立刻抓一张整屏 + 四扇门各自的外扩裁剪。
    #   为什么必须有：① "门到底画在哪、被谁盖住"只有看图能定；
    #   ② 只靠方形区域的黑占比会把"任务栏/对话框/气泡"误算成门的像素。
    shots = []
    try:
        import cv2
        pm = _scr.grabWindow(0)
        im = pm.toImage()
        ptr = im.bits()
        ptr.setsize(im.byteCount())
        full = np.frombuffer(bytes(ptr), np.uint8).reshape(
            im.height(), im.bytesPerLine() // 4, 4)[:, :im.width(), :3]
        full = np.ascontiguousarray(full)

        def _wr(path, arr):
            ok, buf = cv2.imencode('.png', arr)
            if ok:
                with open(path, 'wb') as fh:      # 中文路径必须手写盘
                    fh.write(buf.tobytes())
                shots.append('%s(%d B)' % (os.path.basename(path),
                                           os.path.getsize(path)))

        _wr(os.path.join(OUT, 'probe116_%s_full.png' % TAG), full)
        for L, r in sorted(_RECTS.items()):
            x, y, w, h = r
            pad = max(40, w // 3)
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(_W, x + w + pad)
            y1 = min(_H, y + h + pad)
            _wr(os.path.join(OUT, 'probe116_%s_door%s.png' % (TAG, L)),
                np.ascontiguousarray(full[y0:y1, x0:x1]))
        # 门 B 那一条（含任务栏）：回答"B 是不是被任务栏盖住"
        if 'B' in _RECTS:
            x, y, w, h = _RECTS['B']
            _wr(os.path.join(OUT, 'probe116_%s_trayband.png' % TAG),
                np.ascontiguousarray(full[max(0, y - 40):_H,
                                          max(0, x - 260):min(_W, x + w + 260)]))
    except Exception as e:
        shots.append('抓图失败 %r' % (e,))
    rep.append(u'')
    rep.append(u'★ 肉眼证据已写：%s' % (shots,))


QTimer.singleShot(int(SECS * 1000), _finish)
rc = app.exec_()
say('exit rc=%d rows=%d paints=%d' % (rc, len(_rows), len(_PLOG)))
sys.exit(rc)
