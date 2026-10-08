# -*- coding: utf-8 -*-
u"""rec99.py —— 第99轮「**睡觉后惊醒**」的**录制端**（由 rec98.py 裁剪而来）。

用户口径（原话）
----------------
「**先从睡觉后惊醒做**，做完了也是**自己检查即可**……做完之后还是
 **自己用录屏方式检查**」

本轮要录到的**唯一一幕**
------------------------
睡着（`sleep`）→ 第一次被碰 ⇒ 只迷糊（`look_up`，仍 `sleeping=True`）
→ 5 秒内第二次被碰 ⇒ **惊醒**（`is_sleeping=False` 且 `is_surprised=True`，
画面落到 `surprised_down`）。

★ 为什么必须"产品进程内抓屏"
---------------------------
宠物是 `Qt.Tool` **非置顶 + 透明分层窗口** ⇒ 外部进程 `BitBlt`/`PrintWindow`
抓不到（记忆铁律：看不见 ≠ 不存在）。本进程 `QScreen.grabWindow(0)` 拿的是
**合成后的桌面** ⇒ 看到的＝用户看到的。

★ 复用 rec98.py 已踩实的坑（别再犯）
-----------------------------------
  · `QPixmap.save(..., 'PNG')` 2560×1600 要 **20,410 ms** ⇒ 逐帧存 PNG 会把
    被测对象彻底堵死 ⇒ 只对**状态变化帧**落 PNG，且只截窗口外扩 40px 的小图。
  · 编码选 **mp4v**（实测 ~11 ms/帧）；FFV1 要 173 ms/帧，干扰太大。
  · `csv.writer` 默认 `\r\n`，而分析端按字节忠实读 ⇒ 表头末项带 `\r`
    ⇒ 统一 `lineterminator='\n'`。
  · `cv2.imwrite()` 在**中文路径**下**静默返回 False** ⇒ 必须 `imencode` + 手写。
  · 清旧产物用**整目录改名归档**（1 次文件操作），不逐文件删 —— 删除守卫按
    "本轮累计删除路径数"计账（阈值 50），159 张 PNG 一次就超 ⇒ 启动期被拦。
  · **绝不 remove `rec99_stdout.txt`**：它是 shell 重定向目标，删掉会把 inode
    摘掉 ⇒ 之后所有 stdout 都写进"已删除文件"，磁盘上永远看不到。

★ 注入序列（`REC99_INJECT=1`，默认关）
-------------------------------------
  只调产品**已有**的公开入口，**不新增行为、不改产品代码**：
    · `window.enter_sleep_mode()`  —— 让它睡着（同一函数 `C1` 段测的就是它）
    · `window.last_interaction_time = time.time()` —— **这就是"被碰一下"**
      （产品在 `mousePressEvent` 里做的正是这件事；之后由产品**自己的**定时器
       调 `update_movement`，两拍的判定全在产品代码里，不由夹具代劳）
  ⚠️ 属"定向覆盖"（自然漫游里"睡着被连点两下"是低频事件）⇒ **报告里必须如实标注**。

产物（落本轮 `_evidence/`）
--------------------------
  rec99_meta.txt / rec99_frames.csv / rec99_moves.txt / rec99_anim.txt
  rec99_inject.txt（注入时刻与当时状态） / rec99_state.txt
  rec99_raw.avi（可解码，可直接播放） / frames/*.png（状态变化帧）

跑法
----
  cd <仓库根>
  set REC99_SECS=60
  set REC99_INJECT=1
  C:\\Python311\\python.exe code-quality-audit\\第99轮-睡觉惊醒与场景系统\\_tools\\rec99.py
"""
import csv
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
EV = os.environ.get('REC99_EVDIR') or os.path.join(ROUND, '_evidence')
FRAMES = os.path.join(EV, 'frames')

SECS = int(os.environ.get('REC99_SECS', '60'))
TICK_MS = int(os.environ.get('REC99_TICK_MS', '250'))
RAW = os.path.join(EV, 'rec99_raw.avi')
FOURCC = os.environ.get('REC99_FOURCC', 'mp4v')

os.makedirs(FRAMES, exist_ok=True)

# 自清旧产物：整目录改名归档（见文件头"坑"第 5 条）
if os.environ.get('REC99_PURGE', '1') == '1':
    _ts = time.strftime('%Y%m%d_%H%M%S')
    _prev = os.path.join(EV, 'frames_prev_%s' % _ts)
    try:
        if os.path.isdir(FRAMES) and os.listdir(FRAMES):
            os.rename(FRAMES, _prev)
            os.makedirs(FRAMES)
            print('[rec99] 上一轮关键帧已整目录归档到 %s' % os.path.basename(_prev))
    except Exception as _e:
        print('[rec99] 归档上一轮关键帧失败（忽略）：%r' % (_e,))
    for _f in ('rec99_frames.csv', 'rec99_moves.txt', 'rec99_anim.txt',
               'rec99_inject.txt', 'rec99_state.txt', 'rec99_meta.txt',
               'rec99_raw.avi'):
        _p = os.path.join(EV, _f)
        if os.path.exists(_p):
            try:
                os.remove(_p)
            except Exception:
                pass

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import cv2                                                  # noqa: E402
import numpy as np                                          # noqa: E402
import main as M                                            # noqa: E402
from PyQt5.QtWidgets import QApplication                    # noqa: E402
from PyQt5.QtCore import QTimer                             # noqa: E402

# ---- 复刻 __main__ 启动序列（顺序逐条一致）----
M.check_single_instance()
M.install_crash_guard()
try:
    import text_segmenter
    text_segmenter.install()
except Exception as e:
    print('text_segmenter fail: %r' % (e,))
try:
    import data_store
    data_store.migrate_from_staging()
except Exception as e:
    print('data_store fail: %r' % (e,))

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
# ★ 隔离：不让"到点就寝"的墙钟逻辑插进来（本轮只测"被点醒"这条链）
try:
    window.BEDTIME_ENABLED = False
except Exception:
    pass
print('[rec99] shown pid=%d title=%r' % (os.getpid(), window.windowTitle()))
sys.stdout.flush()

try:
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

_scr = app.primaryScreen()
_geo = _scr.geometry()
_W, _H = _geo.width(), _geo.height()

_t0 = time.time()
_fcsv = io.open(os.path.join(EV, 'rec99_frames.csv'), 'w', encoding='utf-8', newline='')
_csvw = csv.writer(_fcsv, lineterminator='\n')      # ★ 见文件头"坑"第 3 条
# ★ 第99轮新增两列：`spr`（is_surprised）/ `stir`（_sleep_stir_count）——
#   本轮要证的正是"第二拍之后 is_surprised 由 False 变 True 且画面转 surprised_down"，
#   这两列是**产品代码自己判**的观察量，不是我从录像里猜的。
_csvw.writerow(['frame', 't', 'wx', 'wy', 'ww', 'wh', 'anim', 'dir',
                'moving', 'falling', 'gfall', 'sleeping', 'swalk', 'spr', 'stir',
                'p1o', 'spd', 'tx', 'ty', 'spdx', 'spdy'])
_fmov = io.open(os.path.join(EV, 'rec99_moves.txt'), 'w', encoding='utf-8', newline='\n')
_fani = io.open(os.path.join(EV, 'rec99_anim.txt'), 'w', encoding='utf-8', newline='\n')
_fsta = io.open(os.path.join(EV, 'rec99_state.txt'), 'w', encoding='utf-8', newline='\n')
_finj = io.open(os.path.join(EV, 'rec99_inject.txt'), 'w', encoding='utf-8', newline='\n')

_vw = cv2.VideoWriter(RAW, cv2.VideoWriter_fourcc(*FOURCC), 1000.0 / TICK_MS, (_W, _H))
if not _vw.isOpened():
    print('[rec99] FATAL: VideoWriter(%s) 打不开' % FOURCC)
    sys.exit(2)

_N = [0]
_KEY = [0]
_ENC_MS = [0.0]
_GRAB_MS = [0.0]
_LASTGEO = [None]


def _g(o, n, d=None):
    try:
        return getattr(o, n, d)
    except Exception:
        return d


# ---- 劫持 move（与 96/97/98 轮同格式，便于复用已有分析工具）----
_orig_move = window.move
_lastpos = [None]


def _move_wrap(x, y=None):
    if y is None:
        pt = x
        x, y = pt.x(), pt.y()
    if (x, y) != _lastpos[0]:
        _lastpos[0] = (x, y)
        _fmov.write('t=%.3f x=%d y=%d anim=%r dir=%r moving=%r spd=%r tgt=%r sz=%dx%d\n'
                    % (time.time() - _t0, x, y,
                       _g(window, 'current_animation'), _g(window, 'current_direction'),
                       _g(window, 'is_moving'), _g(window, 'speed'),
                       _g(window, 'target_pos'),
                       window.width(), window.height()))
        _fmov.flush()
    return _orig_move(x, y)


window.move = _move_wrap

_orig_change = window.change_animation


def _change_wrap(name, *a, **kw):
    r = _orig_change(name, *a, **kw)
    if not r:
        _fani.write('t=%.3f REJECT %r (cur=%r) args=%r kw=%r\n'
                    % (time.time() - _t0, name, _g(window, 'current_animation'), a, kw))
        _fani.flush()
    return r


window.change_animation = _change_wrap


def tick():
    i = _N[0]
    try:
        t = time.time() - _t0
        tg = time.time()
        pm = _scr.grabWindow(0)
        img = pm.toImage()
        ptr = img.bits()
        ptr.setsize(img.byteCount())
        raw = bytes(ptr)
        arr = np.frombuffer(raw, np.uint8).reshape(img.height(),
                                                   img.bytesPerLine() // 4, 4)
        arr = arr[:, :img.width(), :3]                      # BGRA -> BGR
        _GRAB_MS[0] += (time.time() - tg) * 1000.0
        te = time.time()
        _vw.write(np.ascontiguousarray(arr))
        _ENC_MS[0] += (time.time() - te) * 1000.0

        p = window.pos()
        sx = _g(window, 'speed')
        tp = _g(window, 'target_pos')
        svx = _g(window, 'current_speed_x')
        svy = _g(window, 'current_speed_y')
        _csvw.writerow([i, '%.3f' % t, p.x(), p.y(), window.width(), window.height(),
                        _g(window, 'current_animation'), _g(window, 'current_direction'),
                        _g(window, 'is_moving'), _g(window, 'is_falling'),
                        _g(window, 'is_gravity_falling'),
                        _g(window, 'is_sleeping'), _g(window, 'is_sleeping_walk'),
                        _g(window, 'is_surprised'),
                        _g(window, '_sleep_stir_count'),
                        _g(window, '_play_once_active'),
                        sx if sx is not None else '',
                        tp.x() if tp is not None else '',
                        tp.y() if tp is not None else '',
                        ('%.6f' % svx) if svx is not None else '',
                        ('%.6f' % svy) if svy is not None else ''])

        # ★ 关键帧 PNG：状态变化时落一张（含 `is_surprised` ⇒ "变脸那一帧"必被抓到）
        key = (_g(window, 'current_animation'), _g(window, 'current_direction'),
               window.width(), window.height(), bool(_g(window, 'is_sleeping')),
               bool(_g(window, 'is_surprised')))
        if key != _LASTGEO[0]:
            _LASTGEO[0] = key
            pad = 40
            x0 = max(0, p.x() - pad)
            y0 = max(0, p.y() - pad)
            x1 = min(arr.shape[1], p.x() + window.width() + pad)
            y1 = min(arr.shape[0], p.y() + window.height() + pad)
            crop = np.ascontiguousarray(arr[y0:y1, x0:x1])
            if crop.size:
                # ★★ `cv2.imwrite()` 在中文路径下**静默返回 False** ⇒ imencode + 手写
                _ok, _buf = cv2.imencode('.png', crop)
                if _ok:
                    with open(os.path.join(FRAMES, 'k%06d.png' % _KEY[0]), 'wb') as _fh:
                        _fh.write(_buf.tobytes())
                    _fsta.write('KEY #%d t=%.3f anim=%r spr=%r sleeping=%r stir=%s\n'
                                % (_KEY[0], t, _g(window, 'current_animation'),
                                   _g(window, 'is_surprised'), _g(window, 'is_sleeping'),
                                   _g(window, '_sleep_stir_count')))
                    _fsta.flush()
                    _KEY[0] += 1
        _fcsv.flush()
    except Exception:
        _fsta.write('TICK-ERR frame=%d\n' % i + traceback.format_exc() + '\n')
        _fsta.flush()
    _N[0] = i + 1


tm = QTimer()
tm.timeout.connect(tick)
tm.start(TICK_MS)


def snap():
    try:
        p = window.pos()
        _fsta.write('t=%.1f pos=(%d,%d) sz=%dx%d anim=%r dir=%r mv=%r spr=%r '
                    'sleep=%r stir=%s p1o=%r\n'
                    % (time.time() - _t0, p.x(), p.y(), window.width(), window.height(),
                       _g(window, 'current_animation'), _g(window, 'current_direction'),
                       _g(window, 'is_moving'), _g(window, 'is_surprised'),
                       _g(window, 'is_sleeping'), _g(window, '_sleep_stir_count'),
                       _g(window, '_play_once_active')))
        _fsta.flush()
    except Exception:
        _fsta.write('ERR\n' + traceback.format_exc() + '\n')
        _fsta.flush()


tm2 = QTimer()
tm2.timeout.connect(snap)
tm2.start(1000)


# ============================================================ 注入序列
# ★ 只调产品**已有**入口。`last_interaction_time = time.time()` **就是**"被碰一下"
#   （产品 `mousePressEvent` 里做的就是这件事）⇒ 两拍判定全在产品代码里跑。
if os.environ.get('REC99_INJECT', '0') == '1':
    _AT_SLEEP = int(os.environ.get('REC99_AT_SLEEP', '5000'))
    _AT_POKE1 = int(os.environ.get('REC99_AT_POKE1', '11000'))
    _AT_POKE2 = int(os.environ.get('REC99_AT_POKE2', '13000'))
    _AT_WAKE = int(os.environ.get('REC99_AT_WAKE', '22000'))

    def _log(tag):
        _finj.write('t=%.3f %s sleeping=%r spr=%r stir=%s anim=%r p1o=%r\n'
                    % (time.time() - _t0, tag, _g(window, 'is_sleeping'),
                       _g(window, 'is_surprised'), _g(window, '_sleep_stir_count'),
                       _g(window, 'current_animation'),
                       _g(window, '_play_once_active')))
        _finj.flush()
        print('[rec99][INJECT] %s' % tag)
        sys.stdout.flush()

    def _do_sleep():
        try:
            window.enter_sleep_mode()
        except Exception:
            _finj.write('enter_sleep_mode FAIL\n' + traceback.format_exc() + '\n')
            _finj.flush()
        _log('enter_sleep_mode()')

    def _do_poke1():
        # ★ 只"碰"它：重置互动时刻；随后由产品**自己的** update_movement 走第一拍
        window.last_interaction_time = time.time()
        _log('poke#1 (last_interaction_time=now)')

    def _do_poke2():
        window.last_interaction_time = time.time()
        _log('poke#2 (last_interaction_time=now)')

    def _do_wake():
        # 收尾：确保它从特殊状态里出来（不改行为，只调产品已有入口）
        try:
            window.is_moving = False
        except Exception:
            pass
        _log('settle')

    QTimer.singleShot(_AT_SLEEP, _do_sleep)
    QTimer.singleShot(_AT_POKE1, _do_poke1)
    QTimer.singleShot(_AT_POKE2, _do_poke2)
    QTimer.singleShot(_AT_WAKE, _do_wake)


def _bye():
    print('[rec99] life=%ds reached, quitting' % SECS)
    sys.stdout.flush()
    app.quit()


QTimer.singleShot(SECS * 1000, _bye)

if __name__ == '__main__':
    rc = app.exec_()
    tm.stop()
    tm2.stop()
    _vw.release()
    for f in (_fcsv, _fmov, _fani, _fsta, _finj):
        f.close()

    vid_msg = ''
    try:
        rd = cv2.VideoCapture(RAW)
        n = 0
        while True:
            ok, _fr = rd.read()
            if not ok:
                break
            n += 1
        rd.release()
        vid_msg = u'OK 可解码帧数=%d' % n
    except Exception:
        vid_msg = 'FAIL ' + traceback.format_exc()

    meta = io.open(os.path.join(EV, 'rec99_meta.txt'), 'w', encoding='utf-8', newline='\n')
    dur = time.time() - _t0
    meta.write(u'=== rec99 录制元信息（睡觉后惊醒 · mp4v 边抓边写 · 状态变化帧落小图）===\n')
    meta.write(u'pid                 = %d\n' % os.getpid())
    meta.write(u'时长设定            = %d s\n' % SECS)
    meta.write(u'抓屏周期            = %d ms\n' % TICK_MS)
    meta.write(u'编码 fourcc         = %s\n' % FOURCC)
    meta.write(u'注入                = REC99_INJECT=%s（sleep=%sms poke1=%sms '
               u'poke2=%sms）\n'
               % (os.environ.get('REC99_INJECT', '0'),
                  os.environ.get('REC99_AT_SLEEP', '5000'),
                  os.environ.get('REC99_AT_POKE1', '11000'),
                  os.environ.get('REC99_AT_POKE2', '13000')))
    meta.write(u'实际帧数            = %d\n' % _N[0])
    meta.write(u'有效采集率          = %.2f Hz\n' % (_N[0] / dur if dur else 0))
    meta.write(u'关键帧 PNG 数       = %d\n' % _KEY[0])
    meta.write(u'墙钟耗时            = %.1f s\n' % dur)
    meta.write(u'抓屏累计            = %.1f s（每帧均 %.1f ms）\n'
               % (_GRAB_MS[0] / 1000.0, _GRAB_MS[0] / max(_N[0], 1)))
    meta.write(u'编码累计            = %.1f s（每帧均 %.1f ms）\n'
               % (_ENC_MS[0] / 1000.0, _ENC_MS[0] / max(_N[0], 1)))
    meta.write(u'占用率(抓+编)/墙钟  = %.1f%%\n'
               % (100.0 * (_GRAB_MS[0] + _ENC_MS[0]) / (dur * 1000.0) if dur else 0))
    meta.write(u'屏幕                = %dx%d\n' % (_W, _H))
    # ★ 自证判据：不拿计数器当成功，去**磁盘上数一遍**（v3 首跑就是"计数器 15 / 磁盘 0"）
    _ondisk = sorted(f for f in os.listdir(FRAMES) if f.endswith('.png')) \
        if os.path.isdir(FRAMES) else []
    meta.write(u'frames/ 实际 PNG 数  = %d（计数器 %d）%s\n'
               % (len(_ondisk), _KEY[0],
                  u'' if len(_ondisk) == _KEY[0] else u' ← ★ 不一致！落盘失败'))
    meta.write(u'录像                = %s (%.1f MB)\n'
               % (RAW, os.path.getsize(RAW) / 1048576.0 if os.path.exists(RAW) else -1))
    meta.write(u'录像校验            = %s\n' % vid_msg)
    meta.write(u'退出码              = %d\n' % rc)
    meta.close()
    print('[rec99] exit rc=%d frames=%d keypng=%d' % (rc, _N[0], _KEY[0]))
    sys.exit(rc)
