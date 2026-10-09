# -*- coding: utf-8 -*-
u"""recon99b.py —— 第99轮「**场景系统**」真机侦察（只读，不改任何产品代码）。

为什么要有它
------------
用户口径（本轮逐字）：
    「那个场景系统就像是**把原作全屏化**似的，但**不是真的全屏，只是说像**哦」

在动手改产品之前，必须先回答三个**只能真机回答**的问题（离线判据全部答不了）：
  1. 现在进一间**真有背景**的房间（`ch1.card_castle.card_castle_1f`）时，
     屏幕上**到底画出了什么**？房间在哪、多大？
  2. **宠物还在吗**？`_show_scene_layer()` 每帧 `canvas.raise_()` ⇒ 画布在宠物
     **之上**；若房间背景正压在宠物身上，宠物就"消失"了（= 用户会立刻报的 bug）。
     ⇒ 用 **Win32 z 序枚举**（`GetTopWindow`+`GetWindow(GW_HWNDNEXT)`）量出
     `scene_canvas` 与宠物主窗的**真实前后关系**（几何/标志位量不出这个）。
  3. `_place_scene_layer()` 把画布摆在哪？（"以宠物为中心 + 四向钳制"）

★ 为什么"进程内抓屏"
    宠物是 `Qt.Tool` 非置顶 + 透明分层窗口 ⇒ 外部 `BitBlt/PrintWindow` 抓不到。
    本进程 `QScreen.grabWindow(0)` 拿的是**合成后的桌面** ⇒ 看到的＝用户看到的。

★ 不改产品：只**调**产品已有公开入口（`travel_to_scene`），并把只读的内省量落盘。

产物（落 `_evidence/recon/`）
-----------------------------
  recon99b_shots/*.png    每秒一张（缩到 1280 宽，PNG 存盘便宜）
  recon99b_state.txt      每秒一行：画布几何/可见/view_size/相机/宠物几何 + z 序
  recon99b_meta.txt       元信息（屏幕、时长、退出码等）

跑法
----
  cd <仓库根>
  set RECON99_SCENE=ch1.card_castle.card_castle_1f
  set RECON99_SECS=30
  C:\\Python311\\python.exe code-quality-audit\\第99轮-睡觉惊醒与场景系统\\_tools\\recon99b.py
"""
import ctypes
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
EV = os.environ.get('RECON99_EVDIR') or os.path.join(ROUND, '_evidence', 'recon')
SHOTS = os.path.join(EV, 'recon99b_shots')

SECS = int(os.environ.get('RECON99_SECS', '30'))
SHOT_EVERY = int(os.environ.get('RECON99_SHOT_EVERY', '1'))     # 秒
GO_AT = int(os.environ.get('RECON99_GO_AT', '6'))               # 第几秒切场景
SCENE = os.environ.get('RECON99_SCENE', 'ch1.card_castle.card_castle_1f')
SHOT_W = int(os.environ.get('RECON99_SHOT_W', '1280'))

os.makedirs(SHOTS, exist_ok=True)

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import main as M                                                  # noqa: E402
from PyQt5.QtWidgets import QApplication                           # noqa: E402
from PyQt5.QtCore import QTimer                                    # noqa: E402

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
try:
    window.BEDTIME_ENABLED = False          # 隔离"到点就寝"（与 rec99 同一条隔离）
except Exception:
    pass
# ★ 隔离 NPC 自主移动：`npc_intent.decide()` 的抖动叠真实时钟 ⇒ 观察量永不可复现
try:
    M.RalseiPet.NPC_AUTONOMOUS_MOVE = False
except Exception:
    pass

print('[recon99b] shown pid=%d' % os.getpid())
sys.stdout.flush()

try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

_scr = app.primaryScreen()
_geo = _scr.geometry()
_W, _H = _geo.width(), _geo.height()


def _g(o, n, d=None):
    try:
        return getattr(o, n, d)
    except Exception:
        return d


# ------------------------------------------------------------------ z 序
_u32 = ctypes.windll.user32
_GW_HWNDNEXT = 2
_GW_HWNDPREV = 3


def _zorder_map():
    """枚举顶层窗口的真实 z 序 → `{hwnd: 序号}`（0 = 最上）。

    ★ 这是**几何与标志位都量不出来**的那个量：两个窗口谁的 `size` 都可能是
      640×480，但"谁盖住谁"只由 z 序决定。
    """
    order = {}
    try:
        h = _u32.GetTopWindow(None)
        i = 0
        while h and i < 4000:
            order[int(h)] = i
            h = _u32.GetWindow(h, _GW_HWNDNEXT)
            i += 1
    except Exception:
        pass
    return order


def _hwnd(w):
    try:
        return int(w.winId())
    except Exception:
        return -1


def _cls(h):
    """窗口类名（用来分辨 `Qt5152QWindowToolSaveBits` 之类的真身）。"""
    try:
        buf = ctypes.create_unicode_buffer(256)
        _u32.GetClassNameW(int(h), buf, 256)
        return buf.value
    except Exception:
        return ''


def _title(h):
    try:
        buf = ctypes.create_unicode_buffer(512)
        _u32.GetWindowTextW(int(h), buf, 512)
        return buf.value
    except Exception:
        return ''


_fsta = io.open(os.path.join(EV, 'recon99b_state.txt'), 'w',
                encoding='utf-8', newline='\n')
_t0 = time.time()
_N = [0]
_SHOT = [0]


def _line(tag):
    try:
        canvas = _g(window, 'scene_canvas')
        cam = window.__dict__.get('_scene_camera')
        rect = _g(window, '_virtual_screen_rect')()
        zo = _zorder_map()
        hw_c = _hwnd(canvas) if canvas is not None else -1
        hw_p = _hwnd(window)
        hw_o = _hwnd(_g(window, 'bubble_overlay'))
        parts = [
            't=%.2f %s' % (time.time() - _t0, tag),
            'scene=%r' % (_g(window, 'current_scene'),),
            'pet=(%d,%d %dx%d)' % (window.pos().x(), window.pos().y(),
                                   window.width(), window.height()),
            'canvas_vis=%r' % (_g(canvas, 'isVisible'),),
            'canvas_geo=%r' % (_g(canvas, 'geometry')().getRect(),),
            'canvas_view=%r' % (_g(canvas, 'view_size')(),),
            'canvas_drawn=%r' % (_g(canvas, 'last_drawn'),),
            'canvas_cls=%r' % (_cls(hw_c),),
            'cam=%r' % (cam.rect if cam is not None else None,),
            'viewport=%r' % (_g(_g(window, 'scene'), 'plan_viewport')(),),
            'vscr=%r' % ((rect.x(), rect.y(), rect.width(), rect.height())
                         if rect is not None else None,),
            'z_canvas=%r z_pet=%r z_bubble=%r' % (zo.get(hw_c), zo.get(hw_p),
                                                  zo.get(hw_o)),
            'pet_above_canvas=%r' % (
                (zo.get(hw_p) is not None and zo.get(hw_c) is not None
                 and zo[hw_p] < zo[hw_c]),),
            'pet_cls=%r' % (_cls(hw_p),),
            'pet_title=%r' % (_title(hw_p),),
        ]
        _fsta.write(' | '.join(parts) + '\n')
        _fsta.flush()
    except Exception:
        _fsta.write('ERR\n' + traceback.format_exc() + '\n')
        _fsta.flush()


def snap_shot(tag):
    try:
        pm = _scr.grabWindow(0)
        if SHOT_W and pm.width() > SHOT_W:
            from PyQt5.QtCore import Qt as _Qt
            pm = pm.scaledToWidth(SHOT_W, _Qt.FastTransformation)
        p = os.path.join(SHOTS, 's%03d_%s.png' % (_SHOT[0], tag))
        ok = pm.save(p, 'PNG')
        _SHOT[0] += 1
        print('[recon99b] shot %s ok=%r' % (os.path.basename(p), ok))
        sys.stdout.flush()
    except Exception as e:
        print('[recon99b] shot FAIL %r' % (e,))
        sys.stdout.flush()


def tick():
    _line('')
    _N[0] += 1


tm = QTimer()
tm.timeout.connect(tick)
tm.start(1000)


def _go():
    _line('BEFORE-TRAVEL')
    snap_shot('before')
    try:
        ok = window.travel_to_scene(SCENE)
        print('[recon99b] travel_to_scene(%r) -> %r' % (SCENE, ok))
    except Exception:
        print('[recon99b] travel FAIL\n' + traceback.format_exc())
    sys.stdout.flush()
    _line('AFTER-TRAVEL')

    def _end():
        _line('AFTER-TRAVEL+2s')
        snap_shot('after2')
        _line('AFTER-TRAVEL+4s')
        snap_shot('after4')
    QTimer.singleShot(2000, _end)


QTimer.singleShot(GO_AT * 1000, _go)


def _shot_loop():
    # 切场景之后每 SHOT_EVERY 秒补一张（覆盖整个"稳定态"）
    if time.time() - _t0 > GO_AT:
        snap_shot('loop')


if SHOT_EVERY > 0:
    tms = QTimer()
    tms.timeout.connect(_shot_loop)
    tms.start(SHOT_EVERY * 1000)


def _bye():
    print('[recon99b] life=%ds reached' % SECS)
    sys.stdout.flush()
    app.quit()


QTimer.singleShot(SECS * 1000, _bye)

if __name__ == '__main__':
    rc = app.exec_()
    tm.stop()
    _fsta.close()
    meta = io.open(os.path.join(EV, 'recon99b_meta.txt'), 'w',
                   encoding='utf-8', newline='\n')
    meta.write(u'=== recon99b 元信息（场景系统真机侦察）===\n')
    meta.write(u'屏幕           = %dx%d\n' % (_W, _H))
    meta.write(u'目标场景       = %s\n' % SCENE)
    meta.write(u'切场景时刻     = 第 %d 秒\n' % GO_AT)
    meta.write(u'时长设定       = %d s\n' % SECS)
    meta.write(u'状态行数       = %d\n' % _N[0])
    _on = sorted(f for f in os.listdir(SHOTS) if f.endswith('.png'))
    meta.write(u'shots/ 实际数   = %d（计数器 %d）\n' % (len(_on), _SHOT[0]))
    for f in _on:
        meta.write(u'   %s  %.1f KB\n'
                   % (f, os.path.getsize(os.path.join(SHOTS, f)) / 1024.0))
    meta.write(u'退出码         = %d\n' % rc)
    meta.close()
    print('[recon99b] exit rc=%d lines=%d shots=%d' % (rc, _N[0], _SHOT[0]))
    sys.exit(rc)
