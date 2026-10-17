# -*- coding: utf-8 -*-
u"""diag96_exit.py —— 定位 `rec96` **退出期 0xC0000005** 的故障点（v2）。

背景（第115轮 replay115 实测）
------------------------------
  `rec96.py` 在真机模式下自报 `exit rc=0`、`frames=1116 keypng=297`、
  录像 1116 帧全可解码、`rec96_meta.txt` 也写全了 —— 但**进程退出码 =
  3221225477（0xC0000005，ACCESS_VIOLATION）**。
  ⇒ 故障不在录制逻辑，在 `app.exec_()` **返回之后**（收尾 / 解释器终结期）。

★ v1 的坑（已修）
-----------------
  v1 用 `DIAG96_SECS=6` 短跑，结果 `frames=1` —— 因为 **jieba 首次建词典会
  在事件循环里阻塞约 15 s**（实测：`shown` 20:47:55 → 单发计时器直到 20:48:10
  才触发）。⇒ 短跑**根本没走过逐帧录制这条路**，`_vw.write()` 只调了 1 次，
  而真机那轮是 1116 次 —— 拿它当"writer 路径已验证"是**假绿**。
  ⇒ v2：① `DIAG96_PREWARM=1`（默认）在起窗**之前**把 jieba 词典建好，
     让短跑的帧数与真机同量级；② 补齐 rec96 的三处保真项（关键帧 PNG /
     四个 io 句柄 / `move`+`change_animation` 猴补丁）。

本脚本要回答的三个问题
----------------------
  Q1 故障点在哪一步？      → `DIAG96_MODE` 逐级加料，看哪一级开始崩。
  Q2 是不是"只在解释器终结期"？→ `DIAG96_EXITHOW=osexit` 绕开终结期；
                                绕开后不崩 ⇒ 确认是终结期/静态析构。
  Q3 是录制器引入的，还是产品自身就有？→ `MODE=min`（不加载 cv2）仍崩
                                ⇒ 产品自身退出路径的问题。

模式（DIAG96_MODE）
-------------------
  min     : 不 import cv2/numpy。只起产品窗口 → 退出。            【纯产品退出】
  cv2only : import cv2+numpy，但不建 VideoWriter、不抓帧。        【只多一个 cv2 加载】
  writer  : 每 tick 抓屏写入 VideoWriter，退出时 release。        【+录制链路】
  decode  : = writer，且退出时再用 VideoCapture 解码一遍产物。    【+解码收尾】
  full    : = decode，且写 meta 文件。                           【全等 rec96 尾部】

  `DIAG96_FAITHFUL=1`（默认）额外打开 rec96 的三处保真项。

产物：DIAG96_OUT（默认 E:\\Download\\_tmp\\rec96diag\\）

跑法
----
  set DIAG96_MODE=full
  set DIAG96_SECS=120
  C:\\Python311\\python.exe -X faulthandler ^
      code-quality-audit\\第96轮-用户视角录制复核\\_tools\\diag96_exit.py
"""
import io
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')

MODE = os.environ.get('DIAG96_MODE', 'full').strip().lower()
SECS = int(os.environ.get('DIAG96_SECS', '8'))
EXITHOW = os.environ.get('DIAG96_EXITHOW', 'sys').strip()
SANDBOX = os.environ.get('DIAG96_SANDBOX', '1') == '1'
FAITHFUL = os.environ.get('DIAG96_FAITHFUL', '1') == '1'
PREWARM = os.environ.get('DIAG96_PREWARM', '1') == '1'
OUT = os.environ.get('DIAG96_OUT', r'E:\Download\_tmp\rec96diag')

assert MODE in ('min', 'cv2only', 'writer', 'decode', 'full'), MODE
assert EXITHOW in ('sys', 'osexit'), EXITHOW
os.makedirs(OUT, exist_ok=True)

NEED_CV2 = MODE in ('cv2only', 'writer', 'decode', 'full')
NEED_WRITE = MODE in ('writer', 'decode', 'full')
NEED_DECODE = MODE in ('decode', 'full')
FRAMES = os.path.join(OUT, 'frames')

RAW = os.path.join(OUT, 'diag96_raw.avi')
TICK_MS = 500


def _say(msg):
    sys.stdout.write('[diag96] %s\n' % msg)
    sys.stdout.flush()


_say('MODE=%s EXITHOW=%s SANDBOX=%s FAITHFUL=%s PREWARM=%s SECS=%d'
     % (MODE, EXITHOW, SANDBOX, FAITHFUL, PREWARM, SECS))
_say('python=%s' % sys.version.replace('\n', ' '))
_say('OUT=%s' % OUT)

# ---- ★★★ 沙箱（真源里的**四个**测试闸，少一个就漏）----
#   v2 之前只用了 `RALSEI_DATA_DIR` + `data_store.vault_root=None` 两件，
#   实测**漏**：产品照样写了 `E:\RalseiMemory\memory.json`（2026-10-16 20:50:06）。
#   根因：`data_store` 只是**包装层**，真正的路径真源是 `memory_store`：
#     · `data_store.vault_root()` = `memory_store.find_device_dir()`
#     · 记忆系统**直接**用 `memory_store`，绕开了 `data_store` 的猴补丁
#     · `find_device_dir()` 里 **`RALSEI_MEMORY_DIR`（ENV_DIR）优先级最高**，
#       命中即原样返回 ⇒ 这才是能真正拦住设备目录的那一道。
#   ⇒ 四闸齐下：DATA_DIR（中转站）/ MEMORY_DIR（设备目录）/ DESKTOP（兜底）/
#     外加 vault_root 猴补丁（守 `data_store` 直连路径）。
#   ⇒ 拦没拦住**不靠自称**：跑完用 `_shared/vault_guard.py diff` 独立复核指纹。
_SANDBOX_DIR = None
if SANDBOX:
    import tempfile
    _SANDBOX_DIR = tempfile.mkdtemp(prefix='diag96_data_')
    _vault = os.path.join(_SANDBOX_DIR, 'vault')
    _staging = os.path.join(_SANDBOX_DIR, 'staging')
    _desk = os.path.join(_SANDBOX_DIR, 'desktop')
    for _d in (_vault, _staging, _desk):
        os.makedirs(_d, exist_ok=True)
    os.environ['RALSEI_MEMORY_DIR'] = _vault      # ★ 设备目录（真源头）
    os.environ['RALSEI_DATA_DIR'] = _staging      # ★ 中转站
    os.environ['RALSEI_DESKTOP'] = _desk          # ★ 桌面兜底目录
    _say('沙箱 = %s（vault/staging/desktop 三子目录）' % _SANDBOX_DIR)

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

if NEED_CV2:
    import cv2                                                  # noqa: E402
    import numpy as np                                          # noqa: E402
    _say('cv2 %s build-GUI=%s' % (
        cv2.__version__,
        [l.strip() for l in cv2.getBuildInformation().splitlines()
         if l.strip().startswith('GUI:')]))
else:
    # ★ 负控制：确认"不加载 cv2"这一前提真的成立
    _say('cv2 in sys.modules (before main import) = %s'
         % ('cv2' in sys.modules))

import main as M                                              # noqa: E402
from PyQt5.QtWidgets import QApplication                      # noqa: E402
from PyQt5.QtCore import QTimer                               # noqa: E402

_say('cv2 in sys.modules (after main import) = %s'
     % ('cv2' in sys.modules))

# ---- 复刻 __main__ 启动序列 ----
M.check_single_instance()
M.install_crash_guard()

_ts = time.time()
try:
    import text_segmenter
    text_segmenter.install()
except Exception as e:
    _say('text_segmenter fail: %r' % (e,))
if PREWARM:
    # ★ v2 新增：把"首次建词典"的 ~15 s 挪到起窗之前，否则短跑被它吃掉整段
    try:
        import jieba
        jieba.initialize()
        _say('jieba 预建完成 +%.1fs' % (time.time() - _ts))
    except Exception as e:
        _say('jieba 预热失败（继续）: %r' % (e,))

try:
    import data_store
    if SANDBOX:
        # ★ 第四闸：把 vault 成"取不到" ⇒ 连 `data_store` 直连路径也断
        data_store.vault_root = lambda create=True: None
    _say('data_store: %s' % (data_store.describe(),))
    data_store.migrate_from_staging()
except Exception as e:
    _say('data_store fail: %r' % (e,))

# ★ 正控：把"记忆系统实际会用的目录"打出来 —— 必须落在沙箱里。
#   只打 `data_store` 是不够的（它只是包装层，见上面沙箱注释）。
try:
    import memory_store as _ms
    _mdir, _isdev, _dev = _ms.default_memory_dir()
    _say('memory_store.default_memory_dir() = %r  is_device=%s'
         % (_mdir, _isdev))
    if SANDBOX and not _mdir.startswith(_SANDBOX_DIR):
        _say('★★★ 沙箱失效！记忆目录不在沙箱内：%s' % _mdir)
except Exception as e:
    _say('memory_store 探针失败: %r' % (e,))

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
_say('shown pid=%d title=%r' % (os.getpid(), window.windowTitle()))

try:
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

_scr = app.primaryScreen()
_g = _scr.geometry()
_W, _H = _g.width(), _g.height()

_t0 = time.time()
_N = [0]
_KEY = [0]
_ENC_MS = [0.0]
_GRAB_MS = [0.0]
_LAST = [None]
_vw = None

if FAITHFUL and NEED_WRITE:
    os.makedirs(FRAMES, exist_ok=True)

# ---- ★ 保真项 1：四个 io 句柄（rec96 全程持有）----
_fcsv = _fmov = _fani = _fsta = None
_csvw = None
if FAITHFUL:
    import csv as _csv
    _fcsv = io.open(os.path.join(OUT, 'diag96_frames.csv'), 'w',
                    encoding='utf-8', newline='')
    _csvw = _csv.writer(_fcsv, lineterminator='\n')
    _csvw.writerow(['frame', 't', 'wx', 'wy', 'ww', 'wh', 'anim', 'dir'])
    _fmov = io.open(os.path.join(OUT, 'diag96_moves.txt'), 'w',
                    encoding='utf-8', newline='\n')
    _fani = io.open(os.path.join(OUT, 'diag96_anim.txt'), 'w',
                    encoding='utf-8', newline='\n')
    _fsta = io.open(os.path.join(OUT, 'diag96_state.txt'), 'w',
                    encoding='utf-8', newline='\n')

if NEED_WRITE:
    _vw = cv2.VideoWriter(RAW, cv2.VideoWriter_fourcc(*'mp4v'),
                          1000.0 / TICK_MS, (_W, _H))
    if not _vw.isOpened():
        _say('FATAL VideoWriter 打不开')
        sys.exit(2)
    _say('VideoWriter 已开 %dx%d' % (_W, _H))


def _g_(o, n, d=None):
    try:
        return getattr(o, n, d)
    except Exception:
        return d


# ---- ★ 保真项 2：猴补丁 window.move / window.change_animation ----
if FAITHFUL:
    _orig_move = window.move
    _lastpos = [None]

    def _move_wrap(x, y=None):
        if y is None:
            pt = x
            x, y = pt.x(), pt.y()
        if (x, y) != _lastpos[0]:
            _lastpos[0] = (x, y)
            if _fmov is not None:
                _fmov.write('t=%.3f x=%d y=%d anim=%r dir=%r moving=%r\n'
                            % (time.time() - _t0, x, y,
                               _g_(window, 'current_animation'),
                               _g_(window, 'current_direction'),
                               _g_(window, 'is_moving')))
                _fmov.flush()
        return _orig_move(x, y)

    window.move = _move_wrap

    _orig_change = window.change_animation

    def _change_wrap(name, *a, **kw):
        r = _orig_change(name, *a, **kw)
        if not r and _fani is not None:
            _fani.write('t=%.3f REJECT %r\n' % (time.time() - _t0, name))
            _fani.flush()
        return r

    window.change_animation = _change_wrap


def _tick():
    i = _N[0]
    try:
        seg = None
        if NEED_WRITE:
            tg = time.time()
            pm = _scr.grabWindow(0)
            img = pm.toImage()
            ptr = img.bits()
            ptr.setsize(img.byteCount())
            raw = bytes(ptr)
            arr = np.frombuffer(raw, np.uint8).reshape(
                img.height(), img.bytesPerLine() // 4, 4)
            arr = arr[:, :img.width(), :3]
            _GRAB_MS[0] += (time.time() - tg) * 1000.0
            te = time.time()
            _vw.write(np.ascontiguousarray(arr))
            _ENC_MS[0] += (time.time() - te) * 1000.0
            seg = arr

        p = window.pos()

        # ---- ★ 保真项 3：关键帧 PNG（cv2.imencode + 手写 bytes）----
        if FAITHFUL and seg is not None:
            key = (_g_(window, 'current_animation'),
                   _g_(window, 'current_direction'),
                   window.width(), window.height(),
                   bool(_g_(window, 'is_sleeping')))
            if key != _LAST[0]:
                _LAST[0] = key
                pad = 40
                x0 = max(0, p.x() - pad)
                y0 = max(0, p.y() - pad)
                x1 = min(seg.shape[1], p.x() + window.width() + pad)
                y1 = min(seg.shape[0], p.y() + window.height() + pad)
                crop = np.ascontiguousarray(seg[y0:y1, x0:x1])
                if crop.size:
                    ok, buf = cv2.imencode('.png', crop)
                    if ok:
                        with open(os.path.join(FRAMES, 'k%06d.png' % _KEY[0]),
                                  'wb') as fh:
                            fh.write(buf.tobytes())
                        _KEY[0] += 1

        if _csvw is not None:
            _csvw.writerow([i, '%.3f' % (time.time() - _t0),
                            p.x(), p.y(), window.width(), window.height(),
                            _g_(window, 'current_animation'),
                            _g_(window, 'current_direction')])
            _fcsv.flush()
    except Exception:
        sys.stdout.write('TICK-ERR\n' + traceback.format_exc() + '\n')
        sys.stdout.flush()
    _N[0] = i + 1


tm = QTimer()
tm.timeout.connect(_tick)
tm.start(TICK_MS)


def _bye():
    _say('life=%ds reached, quitting' % SECS)
    app.quit()


QTimer.singleShot(SECS * 1000, _bye)

if __name__ == '__main__':
    # ===================== 以下是 rec96 的收尾链路，逐级可切 =====================
    _say('STEP-0 enter app.exec_()')
    rc = app.exec_()
    _say('STEP-1 exec returned rc=%d  frames=%d keypng=%d'
         % (rc, _N[0], _KEY[0]))

    tm.stop()
    _say('STEP-2 timers stopped')

    if NEED_WRITE:
        _vw.release()
        _say('STEP-3 VideoWriter released')

    for _f in (_fcsv, _fmov, _fani, _fsta):
        if _f is not None:
            _f.close()
    _say('STEP-3b files closed')

    if NEED_DECODE:
        rd = cv2.VideoCapture(RAW)
        n = 0
        while True:
            ok, _fr = rd.read()
            if not ok:
                break
            n += 1
        rd.release()
        _say('STEP-4 VideoCapture decoded n=%d' % n)

    if MODE == 'full':
        _p = os.path.join(OUT, 'diag96_meta.txt')
        with io.open(_p, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(u'=== diag96 meta ===\n')
            fh.write(u'mode=%s frames=%d keypng=%d\n' % (MODE, _N[0], _KEY[0]))
            fh.write(u'rc=%d\n' % rc)
        _say('STEP-5 meta written')

    _say('STEP-6 about to exit (%s) rc=%d' % (EXITHOW, rc))

    if EXITHOW == 'osexit':
        # ★ 直接 _exit(rc)：**不跑** atexit、不跑解释器终结期、不跑 C++ 静态析构
        os._exit(rc)
    sys.exit(rc)
